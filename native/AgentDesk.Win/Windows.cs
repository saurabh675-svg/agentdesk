// Win32 helpers used by the sidecar: windows, clipboard and UI Automation.

using System.Runtime.InteropServices;
using System.Threading;
using System.Text;
using System.Text.Json.Nodes;

namespace AgentDesk.Win;

internal static class Windows
{
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetClassNameW(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);
    [DllImport("user32.dll")] private static extern bool OpenClipboard(IntPtr hWndNewOwner);
    [DllImport("user32.dll")] private static extern bool CloseClipboard();
    [DllImport("user32.dll")] private static extern IntPtr GetClipboardData(uint format);
    [DllImport("kernel32.dll")] private static extern IntPtr GlobalLock(IntPtr hMem);
    [DllImport("kernel32.dll")] private static extern bool GlobalUnlock(IntPtr hMem);
    [DllImport("kernel32.dll")] private static extern IntPtr GlobalAlloc(uint flags, UIntPtr bytes);
    [DllImport("kernel32.dll")] private static extern IntPtr GlobalReAlloc(IntPtr hMem, UIntPtr bytes, uint flags);
    [DllImport("kernel32.dll")] private static extern bool GlobalFree(IntPtr hMem);
    [DllImport("user32.dll")] private static extern bool EmptyClipboard();
    [DllImport("user32.dll")] private static extern bool SetClipboardData(uint format, IntPtr hMem);

    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    private const uint CF_UNICODETEXT = 13;
    private const uint GMEM_MOVEABLE = 0x0002;

    private static JsonObject DescribeWindow(IntPtr hWnd)
    {
        var title = new StringBuilder(512);
        GetWindowTextW(hWnd, title, title.Capacity);
        var className = new StringBuilder(256);
        GetClassNameW(hWnd, className, className.Capacity);
        GetWindowThreadProcessId(hWnd, out var pid);
        string process;
        try
        {
            process = System.Diagnostics.Process.GetProcessById((int)pid).ProcessName;
        }
        catch
        {
            process = "unknown";
        }
        return new JsonObject
        {
            ["handle"] = hWnd.ToInt64(),
            ["title"] = title.ToString(),
            ["class"] = className.ToString(),
            ["pid"] = pid,
            ["process"] = process,
            ["visible"] = IsWindowVisible(hWnd),
        };
    }

    public static JsonNode? ForegroundWindow()
    {
        var hWnd = GetForegroundWindow();
        return hWnd == IntPtr.Zero ? null : DescribeWindow(hWnd);
    }

    public static JsonNode? ListWindows()
    {
        var windows = new JsonArray();
        EnumWindows((hWnd, _) =>
        {
            if (IsWindowVisible(hWnd))
            {
                var title = new StringBuilder(256);
                GetWindowTextW(hWnd, title, title.Capacity);
                if (title.Length > 0)
                {
                    windows.Add(DescribeWindow(hWnd));
                }
            }
            return true;
        }, IntPtr.Zero);
        return new JsonObject { ["windows"] = windows, ["count"] = windows.Count };
    }

    private static bool TryOpenClipboard()
    {
        // The clipboard is a shared, frequently locked resource: retry briefly.
        for (var attempt = 0; attempt < 10; ++attempt)
        {
            if (OpenClipboard(IntPtr.Zero))
            {
                return true;
            }
            Thread.Sleep(50);
        }
        return false;
    }

    public static JsonNode? ClipboardGet()
    {
        if (!TryOpenClipboard())
        {
            throw new InvalidOperationException("could not open the clipboard");
        }
        try
        {
            var handle = GetClipboardData(CF_UNICODETEXT);
            if (handle == IntPtr.Zero)
            {
                return new JsonObject { ["text"] = "" };
            }
            var pointer = GlobalLock(handle);
            try
            {
                var text = Marshal.PtrToStringUni(pointer) ?? "";
                return new JsonObject { ["text"] = text, ["length"] = text.Length };
            }
            finally
            {
                GlobalUnlock(handle);
            }
        }
        finally
        {
            CloseClipboard();
        }
    }

    public static JsonNode? ClipboardSet(string text)
    {
        if (!TryOpenClipboard())
        {
            throw new InvalidOperationException("could not open the clipboard");
        }
        try
        {
            EmptyClipboard();
            var bytes = (text.Length + 1) * sizeof(char);
            var memory = GlobalAlloc(GMEM_MOVEABLE, (UIntPtr)bytes);
            var pointer = GlobalLock(memory);
            try
            {
                Marshal.Copy(Encoding.Unicode.GetBytes(text + "\0"), 0, pointer, bytes / sizeof(char));
            }
            finally
            {
                GlobalUnlock(memory);
            }
            if (!SetClipboardData(CF_UNICODETEXT, memory))
            {
                GlobalFree(memory);
                throw new InvalidOperationException("SetClipboardData failed");
            }
            return new JsonObject { ["ok"] = true, ["length"] = text.Length };
        }
        finally
        {
            CloseClipboard();
        }
    }
}
