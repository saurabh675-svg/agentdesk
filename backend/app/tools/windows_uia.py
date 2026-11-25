"""Windows UI Automation (UIA) tools for native desktop app control.

Allows AgentDesk to inspect visible windows, enumerate accessibility controls
(buttons, edit fields, tabs), and interact reliably via Win32 UIAutomation
without relying on fragile raw screen coordinates.
"""

from __future__ import annotations

import subprocess
from typing import Any


def list_top_windows() -> list[dict[str, Any]]:
    """List all visible top-level application windows using PowerShell Win32 APIs."""
    ps_script = """
    Add-Type @"
      using System;
      using System.Runtime.InteropServices;
      using System.Text;
      public class User32 {
        [DllImport("user32.dll")]
        public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        [DllImport("user32.dll")]
        public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
        [DllImport("user32.dll")]
        public static extern bool IsWindowVisible(IntPtr hWnd);
        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
      }
"@
    $windows = [System.Collections.Generic.List[PSObject]]::new()
    [User32]::EnumWindows({
        param($hWnd, $lParam)
        if ([User32]::IsWindowVisible($hWnd)) {
            $sb = New-Object System.Text.StringBuilder 256
            $len = [User32]::GetWindowText($hWnd, $sb, 256)
            $title = $sb.ToString().Trim()
            if ($len -gt 0 -and $title -ne "Program Manager") {
                $windows.Add([PSCustomObject]@{ Handle = $hWnd.ToInt64(); Title = $title })
            }
        }
        return $true
    }, [IntPtr]::Zero)
    $windows | ConvertTo-Json -Compress
    """
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=10)
        import json
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            res = data if isinstance(data, list) else [data]
            if res:
                return res

        # Fallback to Get-Process MainWindowTitle query
        ps_fallback = "Get-Process | Where-Object { $_.MainWindowTitle } | Select-Object @{N='Handle';E={$_.MainWindowHandle.ToInt64()}}, @{N='Title';E={$_.MainWindowTitle}} | ConvertTo-Json -Compress"
        proc2 = subprocess.run(["powershell", "-NoProfile", "-Command", ps_fallback], capture_output=True, text=True, timeout=6)
        if proc2.returncode == 0 and proc2.stdout.strip():
            data2 = json.loads(proc2.stdout)
            return data2 if isinstance(data2, list) else [data2]
        return []
    except Exception:
        return []


def uia_inspect_window(window_title: str) -> str:
    """Inspect the accessible UI elements of a target window by partial title."""
    ps_cmd = f"""
    Add-Type -AssemblyName UIAutomationClient
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "{window_title}")
    $win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
    if (-not $win) {{
        $all = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
        foreach ($w in $all) {{
            if ($w.Current.Name -like "*{window_title}*") {{ $win = $w; break }}
        }}
    }}
    if (-not $win) {{ "Window not found: {window_title}"; exit }}
    
    $elements = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    $out = [System.Collections.Generic.List[string]]::new()
    $out.Add("=== Window: " + $win.Current.Name + " ===")
    $count = 0
    foreach ($el in $elements) {{
        if ($el.Current.Name -and $el.Current.ControlType.ProgrammaticName) {{
            $type = $el.Current.ControlType.ProgrammaticName.Replace("ControlType.", "")
            $rect = $el.Current.BoundingRectangle
            $bounds = [math]::Round($rect.X).ToString() + "," + [math]::Round($rect.Y).ToString() + " " + [math]::Round($rect.Width).ToString() + "x" + [math]::Round($rect.Height).ToString()
            $out.Add("- [" + $type + "] '" + $el.Current.Name + "' @ " + $bounds)
            $count++
            if ($count -ge 30) {{ break }}
        }}
    }}
    $out -join "`n"
    """
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
        return proc.stdout.strip() or f"No accessible elements returned for '{window_title}'."
    except Exception as exc:
        return f"UIA inspection error: {exc}"


def _find_window_ps(window_title: str) -> str:
    safe = window_title.replace('"', '`"')
    return f"""
    Add-Type -AssemblyName UIAutomationClient
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $all = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
    $win = $null
    foreach ($w in $all) {{ if ($w.Current.Name -like "*{safe}*") {{ $win = $w; break }} }}
    """


def uia_elements_json(window_title: str, limit: int = 40) -> list[dict[str, Any]]:
    """Return interactive controls of a window as structured JSON (for grounding)."""
    ps_cmd = _find_window_ps(window_title) + f"""
    if (-not $win) {{ "[]"; exit }}
    $elements = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    $out = [System.Collections.Generic.List[PSObject]]::new()
    $count = 0
    foreach ($el in $elements) {{
        $name = $el.Current.Name
        $type = $el.Current.ControlType.ProgrammaticName.Replace("ControlType.", "")
        if ($name -and $type -match "Button|Edit|Hyperlink|TabItem|MenuItem|CheckBox|RadioButton|ListItem|ComboBox") {{
            $rect = $el.Current.BoundingRectangle
            if ($rect.Width -gt 2 -and $rect.Height -gt 2) {{
                $out.Add([PSCustomObject]@{{ index=$count; name=$name; type=$type; x=[math]::Round($rect.X); y=[math]::Round($rect.Y); w=[math]::Round($rect.Width); h=[math]::Round($rect.Height) }})
                $count++
                if ($count -ge {int(limit)}) {{ break }}
            }}
        }}
    }}
    ConvertTo-Json -Compress -InputObject $out
    """
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
        import json

        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            return data if isinstance(data, list) else [data]
        return []
    except Exception:
        return []


def uia_click(window_title: str, element_name: str) -> str:
    """Click a named control via UIA InvokePattern, falling back to its center."""
    safe_name = element_name.replace('"', '`"')
    ps_cmd = _find_window_ps(window_title) + f"""
    if (-not $win) {{ "Window not found: {window_title}"; exit }}
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "{safe_name}")
    $el = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
    if (-not $el) {{
        $all = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
        foreach ($e in $all) {{ if ($e.Current.Name -like "*{safe_name}*") {{ $el = $e; break }} }}
    }}
    if (-not $el) {{ "Element not found: {element_name}"; exit }}
    try {{
        $pattern = $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
        $pattern.Invoke()
        "Invoked '" + $el.Current.Name + "'."
    }} catch {{
        $rect = $el.Current.BoundingRectangle
        $cx = [math]::Round($rect.X + $rect.Width / 2)
        $cy = [math]::Round($rect.Y + $rect.Height / 2)
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($cx, $cy)
        Add-Type @"
          using System;
          using System.Runtime.InteropServices;
          public class Mouse {{
            [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
          }}
"@
        [Mouse]::mouse_event(0x0002, 0, 0, 0, 0)
        [Mouse]::mouse_event(0x0004, 0, 0, 0, 0)
        "Clicked center of '" + $el.Current.Name + "' at ($cx, $cy)."
    }}
    """
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
        return proc.stdout.strip() or f"No result clicking '{element_name}'."
    except Exception as exc:
        return f"UIA click error: {exc}"
