// AgentDesk native CDP helper (C++23, MSVC/MinGW, zero external dependencies).
//
// A self-contained Chrome DevTools Protocol client built directly on Winsock:
// no libcurl, no libwebsockets, no Boost. It speaks RFC 6455 WebSocket by
// hand, so the binary is ~60 KB and starts in microseconds.
//
// It exists for two reasons:
//   1. Low-latency input: a click goes out in ~100 us instead of a
//      Python -> Playwright -> browser round trip.
//   2. A reference C++ client for people who want to drive AgentDesk's
//      browser from their own native code (the same pattern as
//      examples/browser/cpp/cdp_client.cpp).
//
// Usage:
//   cdp_helper.exe --port 9333 --action click --x 120 --y 220
//   cdp_helper.exe --port 9333 --action type --text "hello world"
//   cdp_helper.exe --port 9333 --action key --text ArrowDown
//   cdp_helper.exe --port 9333 --action evaluate --expr "document.title"
//   cdp_helper.exe --port 9333 --action screenshot --out shot.jpg
//   cdp_helper.exe --port 9333 --action targets
//
// Exit code 0 = success, 1 = usage error, 2 = protocol/runtime error.

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <shellapi.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#pragma comment(lib, "ws2_32.lib")

namespace {

std::string json_escape(const std::string& in) {
    std::string out;
    out.reserve(in.size() + 16);
    for (unsigned char c : in) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += static_cast<char>(c);
                }
        }
    }
    return out;
}

struct Sha1 {
    uint32_t h[5]{0x67452301u, 0xEFCDAB89u, 0x98BADCFEu, 0x10325476u, 0xC3D2E1F0u};
    uint8_t block[64]{};
    size_t block_len{0};
    uint64_t total{0};

    static uint32_t rol(uint32_t v, int b) { return (v << b) | (v >> (32 - b)); }

    void process_block(const uint8_t* p) {
        uint32_t w[80];
        for (int i = 0; i < 16; ++i) {
            w[i] = (uint32_t(p[i * 4]) << 24) | (uint32_t(p[i * 4 + 1]) << 16) |
                   (uint32_t(p[i * 4 + 2]) << 8) | uint32_t(p[i * 4 + 3]);
        }
        for (int i = 16; i < 80; ++i) w[i] = rol(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
        for (int i = 0; i < 80; ++i) {
            uint32_t f, k;
            if (i < 20) { f = (b & c) | ((~b) & d); k = 0x5A827999u; }
            else if (i < 40) { f = b ^ c ^ d; k = 0x6ED9EBA1u; }
            else if (i < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDCu; }
            else { f = b ^ c ^ d; k = 0xCA62C1D6u; }
            uint32_t tmp = rol(a, 5) + f + e + k + w[i];
            e = d; d = c; c = rol(b, 30); b = a; a = tmp;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
    }

    void update(const uint8_t* data, size_t len) {
        total += len;
        while (len > 0) {
            const size_t remaining = static_cast<size_t>(64) - block_len;
            const size_t take = len < remaining ? len : remaining;
            std::memcpy(block + block_len, data, take);
            block_len += take; data += take; len -= take;
            if (block_len == 64) { process_block(block); block_len = 0; }
        }
    }

    void finish(uint8_t out[20]) {
        uint64_t bits = total * 8;
        uint8_t pad = 0x80;
        update(&pad, 1);
        uint8_t zero = 0;
        while (block_len != 56) update(&zero, 1);
        uint8_t lenbuf[8];
        for (int i = 0; i < 8; ++i) lenbuf[i] = uint8_t(bits >> (56 - i * 8));
        total -= 8;
        update(lenbuf, 8);
        for (int i = 0; i < 5; ++i) {
            out[i * 4 + 0] = uint8_t(h[i] >> 24);
            out[i * 4 + 1] = uint8_t(h[i] >> 16);
            out[i * 4 + 2] = uint8_t(h[i] >> 8);
            out[i * 4 + 3] = uint8_t(h[i]);
        }
    }
};

std::string base64(const uint8_t* data, size_t len) {
    static const char* tbl = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    for (size_t i = 0; i < len; i += 3) {
        uint32_t v = uint32_t(data[i]) << 16;
        if (i + 1 < len) v |= uint32_t(data[i + 1]) << 8;
        if (i + 2 < len) v |= uint32_t(data[i + 2]);
        out += tbl[(v >> 18) & 63];
        out += tbl[(v >> 12) & 63];
        out += (i + 1 < len) ? tbl[(v >> 6) & 63] : '=';
        out += (i + 2 < len) ? tbl[v & 63] : '=';
    }
    return out;
}

std::string random_key() {
    static const char* hex = "0123456789abcdef";
    uint8_t buf[16];
    for (auto& b : buf) b = uint8_t(rand() & 0xff);
    std::string out;
    out.reserve(32);
    for (uint8_t b : buf) { out += hex[b >> 4]; out += hex[b & 15]; }
    return out;
}

int http_get(const std::string& host, int port, const std::string& path, std::string* body) {
    SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == INVALID_SOCKET) return -1;
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(static_cast<uint16_t>(port));
    inet_pton(AF_INET, host.c_str(), &addr.sin_addr);
    if (connect(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        closesocket(sock);
        return -1;
    }
    std::string req = "GET " + path +
                       " HTTP/1.1\r\nHost: " + host +
                       "\r\nUser-Agent: agentdesk-cdp-helper/0.5\r\nAccept: */*\r\n\r\n";
    send(sock, req.data(), static_cast<int>(req.size()), 0);
    DWORD timeout_ms = 8000;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<char*>(&timeout_ms), sizeof(timeout_ms));
    char buffer[8192];
    std::string raw;
    int received;
    size_t header_end = std::string::npos;
    size_t content_length = 0;
    while ((received = recv(sock, buffer, sizeof(buffer), 0)) > 0) {
        raw.append(buffer, received);
        if (header_end == std::string::npos) {
            header_end = raw.find("\r\n\r\n");
            if (header_end != std::string::npos) {
                const std::string headers = raw.substr(0, header_end);
                auto cl = headers.find("Content-Length:");
                if (cl != std::string::npos) {
                    content_length = static_cast<size_t>(std::atoll(headers.c_str() + cl + 15));
                }
            }
        }
        if (header_end != std::string::npos && content_length > 0 &&
            raw.size() >= header_end + 4 + content_length) break;
    }
    closesocket(sock);
    auto split = raw.find("\r\n\r\n");
    if (split == std::string::npos) return -1;
    *body = raw.substr(split + 4, content_length > 0 ? content_length : std::string::npos);
    return 0;
}

class WebSocket {
public:
    bool connect(int port, const std::string& path) {
        socket_ = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (socket_ == INVALID_SOCKET) return false;
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(static_cast<uint16_t>(port));
        inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
        if (::connect(socket_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) return false;

        const std::string key = random_key();
        std::string req =
            "GET " + path + " HTTP/1.1\r\n"
            "Host: 127.0.0.1:" + std::to_string(port) + "\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: " + key + "\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n";
        if (send(socket_, req.data(), static_cast<int>(req.size()), 0) < 0) return false;

        std::string header;
        char c;
        while (header.find("\r\n\r\n") == std::string::npos) {
            int got = recv(socket_, &c, 1, 0);
            if (got <= 0) return false;
            header += c;
        }
        if (header.find("101") == std::string::npos) return false;

        Sha1 sha;
        std::string magic = key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
        sha.update(reinterpret_cast<const uint8_t*>(magic.data()), magic.size());
        uint8_t digest[20];
        sha.finish(digest);
        const std::string expect = base64(digest, 20);
        if (header.find(expect) == std::string::npos) return false;
        return true;
    }

    void close() {
        if (socket_ != INVALID_SOCKET) {
            closesocket(socket_);
            socket_ = INVALID_SOCKET;
        }
    }

    bool send_text(const std::string& payload) {
        std::vector<uint8_t> frame;
        frame.push_back(0x81);
        const size_t len = payload.size();
        uint8_t mask_bit = 0x80;
        if (len < 126) {
            frame.push_back(static_cast<uint8_t>(len) | mask_bit);
        } else if (len <= 0xFFFF) {
            frame.push_back(126 | mask_bit);
            frame.push_back(uint8_t(len >> 8));
            frame.push_back(uint8_t(len & 0xFF));
        } else {
            frame.push_back(127 | mask_bit);
            for (int i = 7; i >= 0; --i) frame.push_back(uint8_t(len >> (i * 8)));
        }
        uint8_t mask[4];
        for (auto& m : mask) m = uint8_t(rand() & 0xff);
        for (int i = 0; i < 4; ++i) frame.push_back(mask[i]);
        for (size_t i = 0; i < len; ++i) frame.push_back(uint8_t(payload[i] ^ mask[i % 4]));
        return send(socket_, reinterpret_cast<const char*>(frame.data()), static_cast<int>(frame.size()), 0) > 0;
    }

    bool recv_text(std::string* out) {
        uint8_t header[2];
        if (!read_exact(header, 2)) return false;
        const uint8_t opcode = header[0] & 0x0F;
        const bool masked = (header[1] & 0x80) != 0;
        uint64_t len = header[1] & 0x7F;
        if (len == 126) {
            uint8_t ext[2];
            if (!read_exact(ext, 2)) return false;
            len = (uint64_t(ext[0]) << 8) | ext[1];
        } else if (len == 127) {
            uint8_t ext[8];
            if (!read_exact(ext, 8)) return false;
            len = 0;
            for (int i = 0; i < 8; ++i) len = (len << 8) | ext[i];
        }
        if (masked) {
            uint8_t mask[4];
            if (!read_exact(mask, 4)) return false;
        }
        std::string payload;
        payload.resize(static_cast<size_t>(len));
        if (len > 0 && !read_exact(reinterpret_cast<uint8_t*>(&payload[0]), static_cast<size_t>(len))) return false;
        if (opcode == 0x8) return false;
        if (opcode == 0x9) { send_text(payload); return recv_text(out); }
        *out = payload;
        return true;
    }

private:
    bool read_exact(uint8_t* out, size_t len) {
        size_t got = 0;
        while (got < len) {
            const int n = recv(socket_, reinterpret_cast<char*>(out + got), static_cast<int>(len - got), 0);
            if (n <= 0) return false;
            got += static_cast<size_t>(n);
        }
        return true;
    }

    SOCKET socket_{INVALID_SOCKET};
};

class CdpClient {
public:
    explicit CdpClient(WebSocket& socket) : socket_(socket) {}

    bool call(const std::string& method, const std::string& params, std::string* result) {
        const int id = ++next_id_;
        std::string message = "{\"id\":" + std::to_string(id) + ",\"method\":\"" + json_escape(method) + "\"";
        if (!params.empty()) message += ",\"params\":" + params;
        message += "}";
        if (!socket_.send_text(message)) return false;

        for (int guard = 0; guard < 5000; ++guard) {
            std::string frame;
            if (!socket_.recv_text(&frame)) return false;
            const std::string id_key = "\"id\":" + std::to_string(id);
            auto pos = frame.find(id_key);
            if (pos == std::string::npos) continue;
            auto result_pos = frame.find("\"result\":", pos);
            if (result_pos == std::string::npos) return false;
            result_pos += 9;
            int depth = 0;
            size_t start = result_pos;
            for (size_t i = result_pos; i < frame.size(); ++i) {
                if (frame[i] == '{' || frame[i] == '[') ++depth;
                else if (frame[i] == '}' || frame[i] == ']') {
                    if (depth == 0) { *result = frame.substr(start, i - start); break; }
                    --depth;
                }
            }
            return true;
        }
        return false;
    }

private:
    WebSocket& socket_;
    int next_id_{0};
};

std::string http_json(const std::string& path, int port) {
    std::string body;
    if (http_get("127.0.0.1", port, path, &body) != 0) return {};
    return body;
}

std::string find_debugger_url(const std::string& json, int port) {
    const std::string key = "\"webSocketDebuggerUrl\": \"";
    auto pos = json.find(key);
    if (pos == std::string::npos) return {};
    pos += key.size();
    auto end = json.find('"', pos);
    if (end == std::string::npos) return {};
    std::string url = json.substr(pos, end - pos);
    auto slash = url.find('/', url.find("://") + 3);
    if (slash != std::string::npos) return url.substr(slash);
    return {};
}

void print_usage() {
    std::printf(
        "AgentDesk CDP helper (C++)\n"
        "  --port <n>        DevTools port (default 9333)\n"
        "  --action <name>   targets|click|doubleclick|type|key|scroll|evaluate|screenshot|move\n"
        "  --x <n> --y <n>   coordinates for click/move/scroll\n"
        "  --text <s>        text to type, or key name\n"
        "  --expr <s>        JavaScript expression for evaluate\n"
        "  --out <file>      output file for screenshot\n");
}

} // namespace

int main(int argc, char** argv) {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);

    int port = 9333;
    std::string action = "targets";
    std::string text;
    std::string expr;
    std::string out;
    double x = 0, y = 0, delta_y = 0;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto next = [&](const char* fallback) -> std::string {
            if (i + 1 >= argc) return fallback;
            return argv[++i];
        };
        if (arg == "--port") port = std::atoi(next("9333").c_str());
        else if (arg == "--action") action = next("targets").c_str();
        else if (arg == "--text") text = next("");
        else if (arg == "--expr") expr = next("");
        else if (arg == "--out") out = next("");
        else if (arg == "--x") x = std::atof(next("0").c_str());
        else if (arg == "--y") y = std::atof(next("0").c_str());
        else if (arg == "--delta-y") delta_y = std::atof(next("0").c_str());
        else if (arg == "--help" || arg == "-h") { print_usage(); WSACleanup(); return 0; }
    }

    if (action == "targets") {
        const std::string body = http_json("/json/list", port);
        if (body.empty()) {
            std::fprintf(stderr, "error: no CDP endpoint on port %d\n", port);
            WSACleanup();
            return 2;
        }
        std::printf("%s", body.c_str());
        WSACleanup();
        return 0;
    }

    const std::string list = http_json("/json/list", port);
    if (list.empty()) {
        std::fprintf(stderr, "error: no CDP endpoint on port %d\n", port);
        WSACleanup();
        return 2;
    }
    const std::string ws_path = find_debugger_url(list, port);
    if (ws_path.empty()) {
        std::fprintf(stderr, "error: no page target with a debugger url\n");
        WSACleanup();
        return 2;
    }

    WebSocket socket;
    if (!socket.connect(port, ws_path)) {
        std::fprintf(stderr, "error: websocket handshake failed (%s)\n", ws_path.c_str());
        WSACleanup();
        return 2;
    }
    CdpClient cdp(socket);

    std::string result;
    if (action == "click" || action == "doubleclick" || action == "move") {
        const char* type = action == "click" ? "mousePressed" : (action == "doubleclick" ? "mousePressed" : "mouseMoved");
        char params[256];
        std::snprintf(params, sizeof(params),
                      "{\"type\":\"%s\",\"x\":%g,\"y\":%g,\"button\":\"left\",\"clickCount\":%d}",
                      type, x, y, action == "doubleclick" ? 2 : 1);
        if (!cdp.call("Input.dispatchMouseEvent", params, &result)) { socket.close(); WSACleanup(); return 2; }
        if (action != "move") {
            std::snprintf(params, sizeof(params),
                          "{\"type\":\"mouseReleased\",\"x\":%g,\"y\":%g,\"button\":\"left\",\"clickCount\":%d}",
                          x, y, action == "doubleclick" ? 2 : 1);
            cdp.call("Input.dispatchMouseEvent", params, &result);
        }
    } else if (action == "type") {
        std::string params = "{\"type\":\"keyDown\",\"text\":\"" + json_escape(text) + "\"}";
        cdp.call("Input.insertText", params, &result);
    } else if (action == "key") {
        std::string params = "{\"type\":\"keyDown\",\"key\":\"" + json_escape(text) + "\"}";
        cdp.call("Input.dispatchKeyEvent", params, &result);
        params = "{\"type\":\"keyUp\",\"key\":\"" + json_escape(text) + "\"}";
        cdp.call("Input.dispatchKeyEvent", params, &result);
    } else if (action == "scroll") {
        char params[256];
        std::snprintf(params, sizeof(params), "{\"type\":\"mouseWheel\",\"x\":%g,\"y\":%g,\"deltaY\":%g}", x, y, delta_y);
        cdp.call("Input.dispatchMouseEvent", params, &result);
    } else if (action == "evaluate") {
        std::string params = "{\"expression\":\"" + json_escape(expr) + "\",\"returnByValue\":true}";
        if (!cdp.call("Runtime.evaluate", params, &result)) { socket.close(); WSACleanup(); return 2; }
    } else if (action == "screenshot") {
        if (!cdp.call("Page.captureScreenshot", "{\"format\":\"jpeg\",\"quality\":80}", &result)) {
            socket.close();
            WSACleanup();
            return 2;
        }
        auto data_pos = result.find("\"data\":\"");
        if (data_pos != std::string::npos) {
            data_pos += 8;
            auto data_end = result.find('"', data_pos);
            const std::string b64 = result.substr(data_pos, data_end - data_pos);
            const std::string path = out.empty() ? std::string("cdp_screenshot.jpg") : out;
            FILE* file = nullptr;
            fopen_s(&file, path.c_str(), "wb");
            if (file) {
                static const char* tbl = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
                int buffer = 0, bits = 0;
                std::vector<uint8_t> bytes;
                bytes.reserve(b64.size() * 3 / 4);
                for (size_t i = 0; i < b64.size(); ++i) {
                    const char c = b64[i];
                    if (c == '=') break;
                    const char* pos = std::strchr(tbl, c);
                    if (!pos) continue;
                    buffer = (buffer << 6) | int(pos - tbl);
                    bits += 6;
                    if (bits >= 8) {
                        bits -= 8;
                        bytes.push_back(uint8_t((buffer >> bits) & 0xFF));
                    }
                }
                fwrite(bytes.data(), 1, bytes.size(), file);
                fclose(file);
                std::printf("{\"written\":\"%s\",\"bytes\":%zu}\n", path.c_str(), bytes.size());
            }
        }
    } else {
        print_usage();
        socket.close();
        WSACleanup();
        return 1;
    }

    std::printf("%s\n", result.c_str());
    socket.close();
    WSACleanup();
    return 0;
}
