// AgentDesk browser via WebDriver BiDi (W3C standard) — works with
// Selenium 4, Playwright for .NET, and any BiDi client.
//   dotnet new console -o . && dotnet add package Selenium.WebDriver && dotnet run
using System.Text.Json;
using System.Net.WebSockets;
using System.Text;

const string BiDiUrl = "ws://127.0.0.1:8756/api/browser/bidi/ws";
string token = Environment.GetEnvironmentVariable("AGENTDESK_BROWSER_TOKEN")
    ?? (File.Exists(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "AgentDesk", "data", "browser-sdk.token"))
        ? File.ReadAllText(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "AgentDesk", "data", "browser-sdk.token")).Trim()
        : "");

using var socket = new ClientWebSocket();
await socket.ConnectAsync(new Uri(BiDiUrl), CancellationToken.None);

long id = 0;
async Task<JsonElement> Send(string method, object payload)
{
    var request = JsonSerializer.Serialize(new { id = ++id, method, @params = payload });
    var bytes = Encoding.UTF8.GetBytes(request);
    await socket.SendAsync(bytes, WebSocketMessageType.Text, true, CancellationToken.None);

    var buffer = new byte[64 * 1024];
    var builder = new StringBuilder();
    WebSocketReceiveResult result;
    do
    {
        result = await socket.ReceiveAsync(buffer, CancellationToken.None);
        builder.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
    } while (!result.EndOfMessage);

    using var doc = JsonDocument.Parse(builder.ToString());
    return doc.RootElement.Clone();
}

var status = await Send("session.status", new { });
Console.WriteLine("session.status -> " + status);

await Send("session.new", new { capabilities = new { alwaysMatch = new { } } });

await Send("browsingContext.navigate", new { url = "https://example.com" });

var tree = await Send("browsingContext.getTree", new { });
Console.WriteLine("contexts: " + tree.GetProperty("result").GetProperty("contexts").GetArrayLength());

var script = await Send("script.evaluate", new
{
    expression = "document.title",
    target = new { context = "active" },
    awaitPromise = false
});
Console.WriteLine("title -> " + script.GetProperty("result").GetProperty("result"));

// Pointer + key actions (arrow keys, clicks, typing) through the standard.
await Send("input.performActions", new
{
    actions = new[]
    {
        new
        {
            type = "key",
            id = "keyboard",
            actions = new object[]
            {
                new { type = "keyDown", value = "ArrowDown" },
                new { type = "keyUp", value = "ArrowDown" }
            }
        }
    }
});

var shot = await Send("browsingContext.captureScreenshot", new { });
Console.WriteLine("screenshot bytes (base64): " + shot.GetProperty("result").GetProperty("data").GetString()!.Length);

await Send("session.end", new { });
