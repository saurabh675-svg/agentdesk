// AgentDesk browser from C++ over raw Chrome DevTools Protocol.
// Talks to the SAME browser the agent uses (your signed-in sessions included).
//
// Build (pick one websocket library):
//   g++ -std=c++17 -O2 cdp_client.cpp -o cdp_client -lwebsockets -lssl -lcrypto -lpthread
//   g++ -std=c++17 -O2 cdp_client.cpp -o cdp_client -lboost_system -lssl -lcrypto -lpthread
//
// Nothing here needs a Chromium download: AgentDesk already runs the browser.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

// Minimal helpers: HTTP GET (for /json/version) and a tiny WebSocket client.
// The WebSocket part uses libwebsockets when available; see #ifdef below.

static std::string http_get(const std::string& host, int port, const std::string& path) {
    std::string cmd = "curl -s http://" + host + ":" + std::to_string(port) + path;
    std::string out;
    FILE* pipe = _popen(cmd.c_str(), "r");
    if (!pipe) return {};
    char buffer[4096];
    while (fgets(buffer, sizeof(buffer), pipe)) out += buffer;
    _pclose(pipe);
    return out;
}

int main(int argc, char** argv) {
    const int port = (argc > 1) ? std::atoi(argv[1]) : 9333;
    const std::string target = (argc > 2) ? argv[2] : "https://example.com";

    const std::string version = http_get("127.0.0.1", port, "/json/version");
    if (version.empty()) {
        std::cerr << "No DevTools endpoint on port " << port
                  << ". Enable Settings -> Browser -> CDP port, then restart the browser.\n";
        return 1;
    }
    std::cerr << "CDP version info: " << version.substr(0, 200) << "\n";

    // The websocket URL sits in the JSON above, e.g.
    //   "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/browser/<id>"
    std::string ws_url;
    const std::string key = "\"webSocketDebuggerUrl\": \"";
    size_t start = version.find(key);
    if (start != std::string::npos) {
        start += key.size();
        size_t end = version.find('"', start);
        ws_url = version.substr(start, end - start);
    }
    if (ws_url.empty()) {
        std::cerr << "Could not parse webSocketDebuggerUrl\n";
        return 1;
    }
    std::cerr << "Connecting to " << ws_url << "\n";

#ifdef AGENTDESK_USE_LIBWEBSOCKETS
    // ---- libwebsockets implementation -------------------------------------
    // ctx, connect, send JSON commands, read responses.
    extern "C" { /* keep the C header out of the way of the docs */ }
#include <libwebsockets.h>
    struct session { std::string out; bool ready = false; };
    static session* g_session = nullptr;
    static int callback(lws* wsi, enum lws_callback_reasons reason, void* user, void* in,
                        size_t len) {
        (void)wsi; (void)user;
        switch (reason) {
            case LWS_CALLBACK_CLIENT_ESTABLISHED:
                g_session->ready = true;
                break;
            case LWS_CALLBACK_CLIENT_RECEIVE:
                g_session->out.append((char*)in, len);
                break;
            default:
                break;
        }
        return 0;
    }
    struct lws_context_creation_info info;
    memset(&info, 0, sizeof(info));
    info.port = CONTEXT_PORT_NO_LISTEN;
    info.protocols = protocols;   // lws_protocols[] = { "agentdesk-cdp", callback, 0, 0, 0, NULL, 0 }
    info.gid = (gid_t)-1;
    info.uid = (uid_t)-1;
    info.user = nullptr;
    info.options = LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;
    lws_context* ctx = lws_create_context(&info);
    if (!ctx) { std::cerr << "lws context failed\n"; return 1; }
    struct lws_client_connect_info ccinfo;
    memset(&ccinfo, 0, sizeof(ccinfo));
    ccinfo.context = ctx;
    ccinfo.address = "127.0.0.1";
    ccinfo.port = port;
    ccinfo.path = ws_url.substr(ws_url.find("/devtools") + 1).c_str();
    ccinfo.host = "127.0.0.1";
    ccinfo.origin = "http://127.0.0.1";
    ccinfo.protocol = protocols[0].name;
    lws_client_connect_via_info(&ccinfo);
    // Then send:
    //   {"id":1,"method":"Target.createTarget","params":{"url":"..."}}
    //   {"id":2,"method":"Page.navigate","params":{"url":"..."}}
    //   {"id":3,"method":"Runtime.evaluate","params":{"expression":"document.title"}}
    //   {"id":4,"method":"Input.dispatchMouseEvent","params":{"type":"mouseMoved","x":120,"y":220}}
    //   {"id":5,"method":"Input.dispatchKeyEvent","params":{"type":"keyDown","key":"ArrowDown"}}
    lws_context_destroy(ctx);
#else
    std::cerr <<
        "Compile with -DAGENTDESK_USE_LIBWEBSOCKETS (or any websocket lib) for the\n"
        "full client. The commands to send over the websocket are:\n"
        "  Target.createTarget  {\"url\":\"<target>\"}\n"
        "  Page.navigate         {\"url\":\"<target>\"}\n"
        "  Runtime.evaluate      {\"expression\":\"document.title\"}\n"
        "  Input.dispatchMouseEvent {\"type\":\"mousePressed\",\"x\":1,\"y\":2,\"button\":\"left\",\"clickCount\":1}\n"
        "  Input.dispatchKeyEvent    {\"type\":\"keyDown\",\"key\":\"ArrowDown\"}\n";
#endif
    (void)target;
    return 0;
}
