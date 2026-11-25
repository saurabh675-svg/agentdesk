// AgentDesk.Windows — the Windows-native sidecar.
//
// Python is great at orchestration but awkward at Windows-native work: UI
// Automation, clipboard, window enumeration and a *real* console (ConPTY) that
// handles 24-bit colour and shell integration. This sidecar owns those.
//
// Transport: named pipe ("\\.\pipe\agentdesk.win") carrying newline-delimited
// JSON, one request/response per line:
//
//   -> {"id":1,"method":"ping"}
//   <- {"id":1,"ok":true,"result":{"pong":true}}
//
// The Python side (backend/app/win_sidecar.py) spawns it, speaks NDJSON and
// fails soft: if the sidecar is missing, the callers fall back to the pure
// Python implementations.

using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace AgentDesk.Win;

internal static partial class Program
{
    private const string PipeName = "agentdesk.win";
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private static async Task<int> Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--version")
        {
            Console.WriteLine("AgentDesk.Win 0.5.0");
            return 0;
        }
        if (args.Length > 0 && args[0] == "--selftest")
        {
            return SelfTest();
        }

        if (args.Length > 0 && args[0] == "--stdio")
        {
            await ServeStdio();
            return 0;
        }

        var server = new NamedPipeServerStream(
            PipeName,
            PipeDirection.InOut,
            maxNumberOfServerInstances: 4,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous);

        Console.WriteLine($"AgentDesk.Win listening on \\\\.\\pipe\\{PipeName}");
        await using (server)
        {
            while (true)
            {
                await server.WaitForConnectionAsync();
                var local = server;
                server = new NamedPipeServerStream(
                    PipeName, PipeDirection.InOut, 4, PipeTransmissionMode.Byte, PipeOptions.Asynchronous);
                _ = Task.Run(() => HandleClient(local));
            }
        }
    }

    private static async Task ServeStdio()
    {
        using var reader = new StreamReader(Console.OpenStandardInput(), Encoding.UTF8);
        using var writer = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true };
        string? line;
        while ((line = await reader.ReadLineAsync()) is not null)
        {
            if (line.Length == 0)
            {
                continue;
            }
            await writer.WriteLineAsync(Dispatch(line));
        }
    }

    private static async Task HandleClient(NamedPipeServerStream pipe)
    {
        using (pipe)
        {
            using var reader = new StreamReader(pipe, Encoding.UTF8);
            using var writer = new StreamWriter(pipe, new UTF8Encoding(false)) { AutoFlush = true };
            string? line;
            while ((line = await reader.ReadLineAsync()) is not null)
            {
                if (line.Length == 0)
                {
                    continue;
                }
                var response = Dispatch(line);
                await writer.WriteLineAsync(response);
            }
        }
    }

    private static string Dispatch(string line)
    {
        long id = 0;
        try
        {
            var request = JsonNode.Parse(line) as JsonObject;
            if (request is null)
            {
                return Error(0, "invalid json");
            }
            id = request["id"]?.GetValue<long>() ?? 0;
            var method = request["method"]?.GetValue<string>() ?? "";
            var parameters = request["params"] as JsonObject ?? new JsonObject();

            var result = method switch
            {
                "ping" => new JsonObject { ["pong"] = true, ["runtime"] = Environment.Version.ToString(), ["pid"] = Environment.ProcessId },
                "window.list" => Windows.ListWindows(),
                "window.foreground" => Windows.ForegroundWindow(),
                "clipboard.get" => Windows.ClipboardGet(),
                "clipboard.set" => Windows.ClipboardSet(parameters["text"]?.GetValue<string>() ?? ""),
                "terminal.start" => Terminal.Start(parameters),
                "terminal.write" => Terminal.Write(parameters),
                "terminal.stop" => Terminal.Stop(parameters),
                "uia.tree" => Uia.Tree(parameters),
                _ => null,
            };

            if (result is null)
            {
                return Error(id, $"unknown method: {method}");
            }
            return new JsonObject { ["id"] = id, ["ok"] = true, ["result"] = result }.ToJsonString();
        }
        catch (Exception ex)
        {
            return Error(id, ex.Message);
        }
    }

    private static string Error(long id, string message) =>
        new JsonObject { ["id"] = id, ["ok"] = false, ["error"] = message }.ToJsonString();

    private static int SelfTest()
    {
        var checks = new (string Name, Func<JsonNode?> Check)[]
        {
            ("ping", () => new JsonObject { ["pong"] = true }),
            ("foreground", Windows.ForegroundWindow),
            ("windows", Windows.ListWindows),
            ("clipboard.set/get", () =>
            {
                Windows.ClipboardSet("agentdesk-selftest");
                return Windows.ClipboardGet();
            }),
        };

        var failed = 0;
        foreach (var (name, check) in checks)
        {
            try
            {
                check();
                Console.WriteLine($"ok    {name}");
            }
            catch (Exception ex)
            {
                failed++;
                Console.WriteLine($"FAIL  {name}: {ex.Message}");
            }
        }
        Console.WriteLine(failed == 0 ? "SELFTEST_OK" : $"SELFTEST_FAILED:{failed}");
        return failed == 0 ? 0 : 1;
    }
}
