'use client'

import { useMemo, useState } from 'react'
import {
  Activity,
  Archive,
  ArrowUpRight,
  BrainCircuit,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Command,
  Cpu,
  FileCode2,
  FolderOpen,
  Gauge,
  HardDrive,
  LayoutDashboard,
  Maximize2,
  Mic,
  MoreHorizontal,
  Play,
  Power,
  RotateCcw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  Volume2,
  WandSparkles,
  X,
  Zap,
} from 'lucide-react'

type Message = { role: 'retro' | 'user'; text: string; meta?: string }
type QueueItem = { label: string; detail: string; icon: typeof FolderOpen }

const initialMessages: Message[] = [
  { role: 'retro', text: 'Good morning, Alex. All systems nominal. What shall we make happen?', meta: '09:41:08 · CORE' },
  { role: 'user', text: 'Check the Downloads folder for anything I should sort.', meta: '09:41:32 · YOU' },
  { role: 'retro', text: 'I found 18 items. Three are installers, two are images, and one archive is over 2 GB. Want me to group them by type?', meta: '09:41:34 · FILE SCAN' },
]

const quickActions = [
  { label: 'Scan Downloads', icon: Search },
  { label: 'Open workspace', icon: FolderOpen },
  { label: 'System report', icon: Activity },
  { label: 'Tell me a joke', icon: Sparkles },
]

const initialQueue: QueueItem[] = [
  { label: 'Group Downloads by type', detail: 'Pending confirmation', icon: FolderOpen },
  { label: 'Open Focus playlist', detail: 'Ready to run', icon: Play },
  { label: 'Archive old screenshots', detail: 'Scheduled · 14:00', icon: Archive },
]

export default function Page() {
  const [messages, setMessages] = useState(initialMessages)
  const [prompt, setPrompt] = useState('')
  const [activeNav, setActiveNav] = useState('Command center')
  const [brightness, setBrightness] = useState(78)
  const [volume, setVolume] = useState(62)
  const [safeMode, setSafeMode] = useState(true)
  const [queue, setQueue] = useState(initialQueue)
  const [notice, setNotice] = useState('')
  const [confirming, setConfirming] = useState(false)

  const stats = useMemo(() => [
    { label: 'CPU', value: '18%', detail: '4 cores · 2.4 GHz', icon: Cpu },
    { label: 'MEMORY', value: '6.2 GB', detail: 'of 16 GB available', icon: Gauge },
    { label: 'STORAGE', value: '42%', detail: '118 GB free', icon: HardDrive },
  ], [])

  async function sendMessage(value = prompt) {
    const trimmed = value.trim()
    if (!trimmed) return

    setMessages((current) => [
      ...current,
      { role: 'user', text: trimmed, meta: 'NOW · YOU' },
    ])
    setPrompt('')
    setNotice('Processing...')

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed }),
      })

      if (!response.ok) {
        throw new Error('Backend request failed')
      }

      const data = await response.json()
      const reply = data.reply || 'No response from Retro.'

      setMessages((current) => [
        ...current,
        { role: 'retro', text: reply, meta: 'NOW · RETRO' },
      ])
      setNotice('Response received')
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: 'retro', text: 'Retro backend is unavailable. Please make sure the Python server is running on localhost:8000.', meta: 'NOW · RETRO' },
      ])
      setNotice('Backend offline')
    }

    window.setTimeout(() => setNotice(''), 2600)
  }

  function runQueueItem(item: QueueItem) {
    if (item.label.includes('Group')) {
      setConfirming(true)
      return
    }
    setNotice(`${item.label} started`)
    setQueue((current) => current.filter((entry) => entry.label !== item.label))
    window.setTimeout(() => setNotice(''), 2600)
  }

  return (
    <main className="retro-shell">
      <aside className="retro-sidebar">
        <div className="brand-mark" aria-label="Retro home"><span>R</span></div>
        <div className="sidebar-status"><span className="status-dot" />ONLINE</div>
        <nav aria-label="Primary navigation" className="nav-stack">
          {[
            { label: 'Command center', icon: LayoutDashboard },
            { label: 'Memory', icon: BrainCircuit },
            { label: 'Files', icon: FileCode2 },
            { label: 'Automations', icon: WandSparkles },
          ].map(({ label, icon: Icon }) => (
            <button key={label} className={`nav-button ${activeNav === label ? 'active' : ''}`} onClick={() => setActiveNav(label)} aria-current={activeNav === label ? 'page' : undefined}>
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-button"><Settings2 size={18} /><span>Settings</span></button>
          <div className="profile"><div className="avatar">AS</div><div><strong>Alex Stone</strong><small>Admin access</small></div><MoreHorizontal size={16} /></div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p className="eyebrow"><span className="pulse-line" /> RETRO / {activeNav.toUpperCase()}</p><h1>Command center</h1></div>
          <div className="top-actions"><span className="clock"><Clock3 size={15} /> Wednesday, 09:41</span><button className="icon-button" aria-label="Help"><CircleHelp size={18} /></button><button className="power-button" aria-label="Power off"><Power size={17} /></button></div>
        </header>

        <div className="content-grid">
          <section className="conversation-panel panel">
            <div className="panel-heading"><div><span className="section-kicker">LIVE SESSION</span><h2>Talk to Retro</h2></div><button className="text-button" onClick={() => setMessages([])}><RotateCcw size={14} /> Clear</button></div>
            <div className="message-list" aria-live="polite">
              {messages.length === 0 && <div className="empty-state"><Terminal size={28} /><p>Your session is clear.</p><span>Try a quick action or type a command below.</span></div>}
              {messages.map((message, index) => <div className={`message-row ${message.role}`} key={`${message.meta}-${index}`}><div className="message-avatar">{message.role === 'retro' ? 'R' : 'AS'}</div><div className="message-content"><span className="message-meta">{message.meta}</span><p>{message.text}</p>{message.role === 'retro' && index === 2 && <div className="inline-action"><button onClick={() => setConfirming(true)}><Check size={14} /> Group by type</button><button onClick={() => setNotice('No changes made')}>Not now</button></div>}</div></div>)}
            </div>
            <div className="composer"><div className="composer-top"><span className="command-badge"><Command size={13} /> COMMAND MODE</span><span>Use natural language or /commands</span></div><div className="composer-input"><textarea aria-label="Message Retro" value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); sendMessage() } }} placeholder="Ask Retro to do something..." rows={2} /><button className="mic-button" aria-label="Use microphone"><Mic size={17} /></button><button className="send-button" onClick={() => sendMessage()} aria-label="Send command"><Send size={17} /></button></div></div>
          </section>

          <aside className="right-rail">
            <section className="panel telemetry-panel"><div className="panel-heading compact"><div><span className="section-kicker">SYSTEM TELEMETRY</span><h2>All systems nominal</h2></div><Activity size={18} className="green-icon" /></div><div className="stats-grid">{stats.map(({ label, value, detail, icon: Icon }) => <div className="stat-card" key={label}><div className="stat-label"><Icon size={14} />{label}</div><strong>{value}</strong><span>{detail}</span><div className="stat-bar"><i style={{ width: label === 'CPU' ? '18%' : label === 'MEMORY' ? '58%' : '42%' }} /></div></div>)}</div><div className="status-row"><span><span className="status-dot" /> Core active</span><span className="mono">v0.8.4</span></div></section>
            <section className="panel controls-panel"><div className="panel-heading compact"><div><span className="section-kicker">QUICK CONTROLS</span><h2>Environment</h2></div><Zap size={18} className="amber-icon" /></div><label className="range-control"><span><span>Brightness</span><strong>{brightness}%</strong></span><input type="range" min="0" max="100" value={brightness} onChange={(event) => setBrightness(Number(event.target.value))} /></label><label className="range-control"><span><span><Volume2 size={14} /> Volume</span><strong>{volume}%</strong></span><input type="range" min="0" max="100" value={volume} onChange={(event) => setVolume(Number(event.target.value))} /></label><div className="toggle-row"><div><ShieldCheck size={16} /><span><strong>Safe mode</strong><small>Ask before risky actions</small></span></div><button className={`toggle ${safeMode ? 'on' : ''}`} onClick={() => setSafeMode(!safeMode)} aria-pressed={safeMode}><span /></button></div></section>
            <section className="panel queue-panel"><div className="panel-heading compact"><div><span className="section-kicker">TASK QUEUE</span><h2>{queue.length} things in motion</h2></div><button className="text-button" onClick={() => setQueue([])}>Clear all</button></div><div className="queue-list">{queue.length === 0 ? <div className="queue-empty">Queue cleared <Check size={14} /></div> : queue.map((item) => { const Icon = item.icon; return <div className="queue-item" key={item.label}><div className="queue-icon"><Icon size={16} /></div><div><strong>{item.label}</strong><small>{item.detail}</small></div><button className="queue-run" onClick={() => runQueueItem(item)} aria-label={`Run ${item.label}`}><ChevronRight size={16} /></button></div> })}</div></section>
          </aside>
        </div>

        <footer className="quick-bar"><span className="section-kicker">SUGGESTED</span>{quickActions.map(({ label, icon: Icon }) => <button key={label} onClick={() => sendMessage(label)}><Icon size={14} /> {label}<ArrowUpRight size={12} /></button>)}</footer>
      </section>
      {notice && <div className="toast"><Check size={15} /> {notice}</div>}
      {confirming && <div className="modal-backdrop" role="presentation"><div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><button className="modal-close" onClick={() => setConfirming(false)} aria-label="Close"><X size={17} /></button><div className="warning-icon"><ShieldCheck size={22} /></div><span className="section-kicker">CONFIRM ACTION</span><h2 id="confirm-title">Group files in Downloads?</h2><p>Retro will create folders and move 18 items. Nothing will be deleted, but existing folder names may be reused.</p><div className="modal-actions"><button className="secondary-button" onClick={() => setConfirming(false)}>Cancel</button><button className="primary-button" onClick={() => { setConfirming(false); setQueue((current) => current.filter((item) => !item.label.includes('Group'))); setNotice('Files grouped successfully') }}>Continue <ChevronRight size={15} /></button></div></div></div>}
    </main>
  )
}
