// UI Automation (UIA3) tree walking.
//
// The legacy Python implementation choked on deep trees and provider-specific
// elements. .NET's System.Windows.Automation is the supported managed API, so
// the sidecar walks the tree and returns a compact, JSON-friendly structure
// that the agent can act on (name, role, automation id, bounding rect).

using System.Text.Json.Nodes;
using System.Windows.Automation;

namespace AgentDesk.Win;

internal static class Uia
{
    public static JsonNode? Tree(JsonObject parameters)
    {
        var depth = parameters["depth"]?.GetValue<int>() ?? 6;
        var maxNodes = parameters["max"]?.GetValue<int>() ?? 400;

        var root = parameters["handle"]?.GetValue<long>() is long handle && handle != 0
            ? AutomationElement.FromHandle(new IntPtr(handle))
            : AutomationElement.RootElement;

        var nodes = new JsonArray();
        int count = 0;
        Walk(root, 0, depth, maxNodes, nodes, ref count);

        return new JsonObject
        {
            ["nodes"] = nodes,
            ["count"] = count,
            ["truncated"] = count >= maxNodes,
        };
    }

    private static void Walk(AutomationElement element, int level, int maxDepth, int maxNodes, JsonArray output, ref int count)
    {
        if (count >= maxNodes || level > maxDepth)
        {
            return;
        }

        AutomationElement? child = null;
        try
        {
            var name = element.Current.Name ?? "";
            var controlType = element.Current.ControlType?.ProgrammaticName ?? "";
            var automationId = element.Current.AutomationId ?? "";
            var className = element.Current.ClassName ?? "";
            var rect = element.Current.BoundingRectangle;

            var node = new JsonObject
            {
                ["name"] = name,
                ["role"] = controlType.Replace("ControlType.", ""),
                ["automation_id"] = automationId,
                ["class"] = className,
                ["enabled"] = element.Current.IsEnabled,
                ["offscreen"] = element.Current.IsOffscreen,
                ["depth"] = level,
                ["rect"] = new JsonObject
                {
                    ["x"] = rect.X,
                    ["y"] = rect.Y,
                    ["w"] = rect.Width,
                    ["h"] = rect.Height,
                },
            };
            output.Add(node);
            count++;

            child = TreeWalker.RawViewWalker.GetFirstChild(element);
        }
        catch
        {
            return;
        }

        while (child is not null && count < maxNodes)
        {
            Walk(child, level + 1, maxDepth, maxNodes, output, ref count);
            try
            {
                child = TreeWalker.RawViewWalker.GetNextSibling(child);
            }
            catch
            {
                break;
            }
        }
    }
}
