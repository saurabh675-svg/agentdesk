import { useState } from "react"
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  FolderOpen,
  Plus,
  RefreshCw,
  Settings as SettingsIcon,
  Trash2,
} from "lucide-react"
import type { FileNode, Session, WorkspacePayload } from "../types"

interface Props {
  sessions: Session[]
  currentSession: number | null
  workspace: WorkspacePayload
  wsState: "connecting" | "open" | "closed"
  onSelectSession: (id: number) => void
  onNewSession: () => void
  onDeleteSession: (id: number) => void
  onPickFolder: () => void
  onRefreshTree: () => void
  onOpenFile: (path: string) => void
  onOpenSettings: () => void
}

function TreeRow({
  node,
  depth,
  onOpenFile,
  expandAll = false,
}: {
  node: FileNode
  depth: number
  onOpenFile: (path: string) => void
  expandAll?: boolean
}) {
  const [open, setOpen] = useState(depth < 1)
  const isDir = node.type === "dir"
  // While a filter is active, matching folders stay expanded so hits deeper
  // in the tree are actually visible instead of hidden behind a closed row.
  const expanded = expandAll || open
  return (
    <div>
      <button
        className="tree-row"
        style={{ paddingLeft: 8 + depth * 12 }}
        title={node.path}
        aria-expanded={isDir ? expanded : undefined}
        onClick={() => (isDir ? setOpen((value) => !value) : onOpenFile(node.path))}
      >
        {isDir ? (
          <>
            {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            {expanded ? <FolderOpen size={13} className="icon-folder" /> : <Folder size={13} className="icon-folder" />}
          </>
        ) : (
          <>
            <span className="tree-spacer" />
            <FileText size={13} className="icon-file" />
          </>
        )}
        <span className="tree-name">{node.name}</span>
      </button>
      {isDir && expanded && node.children?.map((child) => (
        <TreeRow key={child.path} node={child} depth={depth + 1} onOpenFile={onOpenFile} expandAll={expandAll} />
      ))}
    </div>
  )
}

function timeAgo(seconds: number): string {
  const delta = Date.now() / 1000 - seconds
  if (delta < 60) return "now"
  if (delta < 3600) return `${Math.floor(delta / 60)}m`
  if (delta < 86400) return `${Math.floor(delta / 3600)}h`
  return `${Math.floor(delta / 86400)}d`
}

function filterTree(nodes: FileNode[], query: string): FileNode[] {
  const q = (query || "").trim().toLowerCase()
  if (!q) return nodes
  const visit = (node: FileNode): FileNode | null => {
    // A folder whose own name matches keeps its whole subtree; otherwise only
    // the children that match are kept.
    if (node.name.toLowerCase().includes(q)) return node
    if (node.type === "file") return null
    const kids = (node.children || []).map(visit).filter((n): n is FileNode => n !== null)
    return kids.length > 0 ? { ...node, children: kids } : null
  }
  return nodes.map(visit).filter((n): n is FileNode => n !== null)
}

export default function Sidebar(props: Props) {
  const [fileFilter, setFileFilter] = useState("")
  const folderName = props.workspace.path
    ? props.workspace.path.replace(/[\\/]+$/, "").split(/[\\/]/).pop()
    : "No folder"

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">◆</div>
        <div className="brand-text">
          <strong>AgentDesk</strong>
          <span className="brand-status">
            <i className={`status-dot ${props.wsState}`} />
            {props.wsState === "open" ? "connected" : props.wsState}
          </span>
        </div>
        <button className="icon-button" onClick={props.onOpenSettings} title="Settings" aria-label="Open settings">
          <SettingsIcon size={15} />
        </button>
      </div>

      <div className="workspace-card">
        <div className="workspace-head">
          <FolderOpen size={14} className="icon-folder" />
          <span className="workspace-name" title={props.workspace.path ?? ""}>{folderName}</span>
          <button className="mini-button" onClick={props.onPickFolder} aria-label="Change workspace folder">
            change
          </button>
        </div>
        <div className="workspace-path" title={props.workspace.path ?? ""}>
          {props.workspace.path ?? "Choose a project folder"}
        </div>
      </div>

      <button className="new-chat" onClick={props.onNewSession}>
        <Plus size={14} /> New chat
      </button>

      <div className="section-label">Sessions</div>
      <div className="session-list">
        {props.sessions.map((session) => (
          <div
            key={session.id}
            className={`session-row ${session.id === props.currentSession ? "active" : ""}`}
            onClick={() => props.onSelectSession(session.id)}
          >
            <div className="session-main">
              <span className="session-title">{session.title}</span>
              <span className="session-time">{timeAgo(session.updated_at)}</span>
            </div>
            <button
              className="row-delete"
              title="Delete session"
              aria-label={`Delete session ${session.title}`}
              onClick={(event) => {
                event.stopPropagation()
                props.onDeleteSession(session.id)
              }}
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
        {props.sessions.length === 0 && <div className="empty-hint">No sessions yet</div>}
      </div>

      <div className="section-label files-label">
        Files
        <button className="icon-button tiny" onClick={props.onRefreshTree} title="Refresh files" aria-label="Refresh files">
          <RefreshCw size={11} />
        </button>
      </div>
      <div className="file-filter">
        <input
          className="file-filter-input"
          type="text"
          placeholder="Filter files…"
          value={fileFilter}
          onChange={(event) => setFileFilter(event.target.value)}
          aria-label="Filter files by name"
        />
      </div>
      <div className="file-tree">
        {filterTree(props.workspace.tree, fileFilter).map((node) => (
          <TreeRow
            key={node.path}
            node={node}
            depth={0}
            onOpenFile={props.onOpenFile}
            expandAll={fileFilter.trim() !== ""}
          />
        ))}
        {props.workspace.tree.length === 0 && (
          <div className="empty-hint">Pick a folder to browse files</div>
        )}
        {props.workspace.tree.length > 0 &&
          fileFilter.trim() !== "" &&
          filterTree(props.workspace.tree, fileFilter).length === 0 && (
            <div className="empty-hint">No files match “{fileFilter.trim()}”</div>
          )}
      </div>

      <div className="sidebar-footer">
        <span>v0.1 · local</span>
        <span className="model-chip" title={props.workspace.path ?? ""}>local model</span>
      </div>
    </aside>
  )
}
