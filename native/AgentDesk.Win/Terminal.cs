// ConPTY-backed terminal.
//
// xterm.js needs a real pseudo console on Windows to get 24-bit colour, resize
// notifications and shell integration (OSC 133). The Python side used to
// emulate that with pipes, which loses colour and breaks interactive tools.

using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json.Nodes;

namespace AgentDesk.Win;

internal static class Terminal
{

    [StructLayout(LayoutKind.Sequential)]
    private struct Coord { public short X; public short Y; }

    [StructLayout(LayoutKind.Sequential)]
    private struct ConsoleScreenBufferInfo
    {
        public Coord Size;      // dwSize
        public Coord Cursor;   // dwCursorPosition
        public short Attributes;
        public Coord Window;   // srWindow
        public Coord Maximum;  // dwMaximumWindowSize
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SecurityAttributes
    {
        public int Length;
        public IntPtr Descriptor;
        public bool InheritHandle;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcThreadAttributeList
    {
        public IntPtr Size;
        public IntPtr Buffer;
        public IntPtr Next;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern int CreatePseudoConsole(Coord size, IntPtr input, IntPtr output, uint flags, out IntPtr pseudoConsole);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern int ClosePseudoConsole(IntPtr hPC);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ClosePseudoConsoleInput(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ClosePseudoConsoleOutput(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CreatePipe(out IntPtr read, out IntPtr write, ref SecurityAttributes attributes, uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool InitializeProcThreadAttributeList(IntPtr list, int count, int flags, ref IntPtr size);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool UpdateProcThreadAttribute(IntPtr list, uint flags, IntPtr attribute, IntPtr value, IntPtr size, IntPtr previous, IntPtr returnSize);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern void DeleteProcThreadAttributeList(IntPtr list);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CreateProcessW(
        string? applicationName, StringBuilder commandLine, IntPtr processAttributes, IntPtr threadAttributes,
        bool inheritHandles, uint creationFlags, IntPtr environment, string? currentDirectory,
        ref StartupInfo startupInfo, out ProcessInformation processInformation);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetConsoleScreenBufferInfo(IntPtr handle, out ConsoleScreenBufferInfo info);
    [DllImport("kernel32.dll")] private static extern bool WriteFile(IntPtr handle, byte[] buffer, uint count, out uint written, IntPtr overlapped);
    [DllImport("kernel32.dll")] private static extern bool ReadFile(IntPtr handle, byte[] buffer, uint count, out uint read, IntPtr overlapped);
    [DllImport("kernel32.dll")] private static extern bool ResizePseudoConsole(IntPtr hPC, Coord size);

    [StructLayout(LayoutKind.Sequential)]
    private struct StartupInfo
    {
        public int cb;
        public string? lpReserved;
        public string? lpDesktop;
        public string? lpTitle;
        public int dwX;
        public int dwY;
        public int dwXSize;
        public int dwYSize;
        public int dwXCountChars;
        public int dwYCountChars;
        public int dwFillAttribute;
        public int dwFlags;
        public short wShowWindow;
        public short cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
        public IntPtr lpAttributeList;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessInformation
    {
        public IntPtr Process;
        public IntPtr Thread;
        public int dwProcessId;
        public int dwThreadId;
    }

    private const int EXTENDED_STARTUPINFO_PRESENT = 0x00080000;
    private const int PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016;

    private sealed class Session
    {
        public required string Id { get; init; }
        public required IntPtr PseudoConsole { get; init; }
        public required IntPtr InputRead { get; init; }
        public required IntPtr InputWrite { get; init; }
        public required IntPtr OutputRead { get; init; }
        public required IntPtr OutputWrite { get; init; }
        public required Process Process { get; init; }
        public required StringBuilder Output { get; init; }
    }

    private static readonly Dictionary<string, Session> Sessions = new();
    private static readonly object Gate = new();

    public static JsonNode? Start(JsonObject parameters)
    {
        var id = parameters["id"]?.GetValue<string>() ?? Guid.NewGuid().ToString("N")[..8];
        var shell = parameters["shell"]?.GetValue<string>() ?? "cmd.exe";
        var args = parameters["args"]?.GetValue<string>() ?? "";
        var rows = parameters["rows"]?.GetValue<int>() ?? 30;
        var columns = parameters["cols"]?.GetValue<int>() ?? 120;
        var cwd = parameters["cwd"]?.GetValue<string>() ?? Environment.CurrentDirectory;

        var attributes = new SecurityAttributes { Length = Marshal.SizeOf<SecurityAttributes>() };
        if (!CreatePipe(out var inputRead, out var inputWrite, ref attributes, 0))
        {
            throw new InvalidOperationException("CreatePipe(input) failed");
        }
        if (!CreatePipe(out var outputRead, out var outputWrite, ref attributes, 0))
        {
            throw new InvalidOperationException("CreatePipe(output) failed");
        }

        var size = new Coord { X = (short)columns, Y = (short)rows };
        var hr = CreatePseudoConsole(size, inputRead, outputWrite, 0, out var pseudoConsole);
        if (hr != 0)
        {
            throw new InvalidOperationException($"CreatePseudoConsole failed: HRESULT 0x{hr:X8}");
        }
        // The pseudo console duplicated the pipe handles; close our copies.
        ClosePseudoConsoleInput(inputRead);
        ClosePseudoConsoleOutput(outputWrite);

        var startupInfo = new StartupInfo { cb = Marshal.SizeOf<StartupInfo>() };
        var attributeListSize = IntPtr.Zero;
        InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref attributeListSize);
        var attributeList = Marshal.AllocHGlobal(attributeListSize);
        InitializeProcThreadAttributeList(attributeList, 1, 0, ref attributeListSize);
        if (!UpdateProcThreadAttribute(attributeList, 0, (IntPtr)PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, pseudoConsole, (IntPtr)IntPtr.Size, IntPtr.Zero, IntPtr.Zero))
        {
            throw new InvalidOperationException("UpdateProcThreadAttribute failed");
        }
        startupInfo.dwFlags = EXTENDED_STARTUPINFO_PRESENT;
        startupInfo.lpAttributeList = attributeList;

        var commandLine = new StringBuilder($"{shell} {args}".Trim());
        var created = CreateProcessW(null, commandLine, IntPtr.Zero, IntPtr.Zero, false,
            (uint)EXTENDED_STARTUPINFO_PRESENT, IntPtr.Zero, cwd, ref startupInfo, out var processInfo);
        // ReSharper disable once UnusedVariable
        DeleteProcThreadAttributeList(attributeList);
        Marshal.FreeHGlobal(attributeList);
        if (!created)
        {
            throw new InvalidOperationException($"CreateProcessW failed: {Marshal.GetLastWin32Error()}");
        }

        var process = Process.GetProcessById(processInfo.dwProcessId);
        var session = new Session
        {
            Id = id,
            PseudoConsole = pseudoConsole,
            InputRead = inputRead,
            InputWrite = inputWrite,
            OutputRead = outputRead,
            OutputWrite = outputWrite,
            Process = process,
            Output = new StringBuilder(),
        };

        lock (Gate)
        {
            Sessions[id] = session;
        }

        // Pump the output in the background so the caller can read it later.
        _ = Task.Run(() => Pump(session));

        return new JsonObject
        {
            ["id"] = id,
            ["pid"] = processInfo.dwProcessId,
            ["shell"] = shell,
            ["rows"] = rows,
            ["cols"] = columns,
        };
    }

    private static void Pump(Session session)
    {
        var buffer = new byte[8192];
        while (!session.Process.HasExited)
        {
            uint read;
            if (!ReadFile(session.OutputRead, buffer, (uint)buffer.Length, out read, IntPtr.Zero) || read == 0)
            {
                break;
            }
            lock (session.Output)
            {
                session.Output.Append(Encoding.UTF8.GetString(buffer, 0, (int)read));
                if (session.Output.Length > 512_000)
                {
                    session.Output.Remove(0, session.Output.Length - 256_000);
                }
            }
        }
    }

    public static JsonNode? Write(JsonObject parameters)
    {
        var id = parameters["id"]?.GetValue<string>() ?? "";
        var text = parameters["text"]?.GetValue<string>() ?? "";
        lock (Gate)
        {
            if (!Sessions.TryGetValue(id, out var session))
            {
                throw new KeyNotFoundException($"unknown terminal session: {id}");
            }
            var bytes = Encoding.UTF8.GetBytes(text);
            uint written;
            if (!WriteFile(session.InputWrite, bytes, (uint)bytes.Length, out written, IntPtr.Zero))
            {
                throw new InvalidOperationException("WriteFile failed");
            }
            return new JsonObject { ["written"] = written };
        }
    }

    public static JsonNode? Stop(JsonObject parameters)
    {
        var id = parameters["id"]?.GetValue<string>() ?? "";
        lock (Gate)
        {
            if (!Sessions.Remove(id, out var session))
            {
                return new JsonObject { ["stopped"] = false, ["reason"] = "unknown session" };
            }
            try
            {
                if (!session.Process.HasExited)
                {
                    session.Process.Kill();
                }
            }
            catch
            {
                // already gone
            }
            ClosePseudoConsole(session.PseudoConsole);
            return new JsonObject { ["stopped"] = true };
        }
    }

    public static JsonNode? Read(JsonObject parameters)
    {
        var id = parameters["id"]?.GetValue<string>() ?? "";
        lock (Gate)
        {
            if (!Sessions.TryGetValue(id, out var session))
            {
                throw new KeyNotFoundException($"unknown terminal session: {id}");
            }
            lock (session.Output)
            {
                return new JsonObject { ["text"] = session.Output.ToString() };
            }
        }
    }
}
