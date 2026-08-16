'use client'

import { FormEvent, useState } from 'react'
import { ArrowUpRight, ChevronDown, Command, Copy, Cpu, FileCode2, Gauge, History, LayoutGrid, Library, Menu, Mic, MoreHorizontal, Paperclip, Play, Plus, Radio, Search, Send, Settings2, Sparkles, Terminal, Trash2, Volume2, Wifi, X, Zap } from 'lucide-react'

const initialMessages = [
  { role: 'user', text: 'Design a product launch page for a new AI music tool. Make it feel experimental, fast, and human.', time: '09:41:12' },
  { role: 'retro', text: 'I can turn that into a complete launch system. I’m keeping the language sharp, the energy high, and the interface tactile. Starting with the narrative layer now.', time: '09:41:14', tags: ['NARRATIVE', 'VISUAL SYSTEM'] },
]

const history = ['Untitled session', 'Landing page / music AI', 'Brand voice sprint', 'Interface audit', 'Launch campaign']

export default function Home() {
  const [messages, setMessages] = useState(initialMessages)
  const [input, setInput] = useState('')
  const [activeHistory, setActiveHistory] = useState(0)
  const [running, setRunning] = useState(false)
  const [mode, setMode] = useState('BUILD')
  const [rightOpen, setRightOpen] = useState(true)
  const [brightness, setBrightness] = useState(78)
  const [volume, setVolume] = useState(62)

  async function sendMessage(event: FormEvent) {
    event.preventDefault()
    if (!input.trim() || running) return
    const text = input.trim()
    setMessages((current) => [...current, { role: 'user', text, time: new Date().toLocaleTimeString([], { hour12: false }) }])
    setInput('')
    setRunning(true)
    try {
      const response = await fetch('http://localhost:8000/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text }) })
      const data = await response.json()
      setMessages((current) => [...current, { role: 'retro', text: data.reply || 'Signal received. I’m ready for the next move.', time: new Date().toLocaleTimeString([], { hour12: false }), tags: ['GENERATED'] }])
    } catch {
      setMessages((current) => [...current, { role: 'retro', text: 'Local mode is active. Your brief is queued and ready to shape into a new direction.', time: new Date().toLocaleTimeString([], { hour12: false }), tags: ['LOCAL MODE'] }])
    } finally { setRunning(false) }
  }

  return (
    <main className="app-shell">
      <aside className="side-rail">
        <div className="brand-mark"><span>R</span><div><strong>RETRO</strong><small>AI SYSTEM</small></div></div>
        <button className="new-session" onClick={() => setMessages([])}><Plus data-icon="inline-start" /> New session</button>
        <div className="rail-label"><History /> Recent</div>
        <nav className="history-list">{history.map((item, index) => <button className={activeHistory === index ? 'history-item active' : 'history-item'} key={item} onClick={() => setActiveHistory(index)}><span className="history-dot" />{item}<MoreHorizontal /></button>)}</nav>
        <div className="rail-bottom"><button><Library /> Library</button><button><Settings2 /> System settings</button><div className="user-chip"><div className="avatar">AM</div><span><b>Amish</b><small>Local operator</small></span><ChevronDown /></div></div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div className="crumb"><span className="pulse" /> RETRO / <b>WORKSPACE</b></div><div className="top-actions"><span className="status"><Wifi /> Local engine online</span><button className="icon-btn"><Search /></button><button className="icon-btn" onClick={() => setRightOpen(!rightOpen)}><LayoutGrid /></button></div></header>
        <div className="canvas">
          <div className="canvas-heading"><div><p className="eyebrow">CREATIVE OPERATING SYSTEM <span>v2.4.0</span></p><h1>Make something<br /><em>unexpected.</em></h1></div><div className="run-state"><span className={running ? 'loader' : 'idle-dot'} /> {running ? 'PROCESSING SIGNAL' : 'READY TO GENERATE'}<small>LATENCY 24MS</small></div></div>
          <div className="mode-row"><div className="mode-toggle">{['BUILD', 'EXPLORE', 'REFINE'].map((item) => <button key={item} className={mode === item ? 'selected' : ''} onClick={() => setMode(item)}>{item}</button>)}</div><span className="mode-hint"><Zap /> {mode === 'BUILD' ? 'Output is yours to direct' : mode === 'EXPLORE' ? 'Push into new territory' : 'Tune every detail'}</span></div>
          <div className="conversation">{messages.length === 0 ? <div className="empty-state"><Sparkles /><p>Start with a direction, a problem, or a strange idea.</p></div> : messages.map((message, index) => <article className={message.role === 'user' ? 'message user-message' : 'message retro-message'} key={`${message.time}-${index}`}><div className="message-meta">{message.role === 'user' ? <><span className="mini-avatar">AM</span> YOU</> : <><span className="retro-icon">R</span> RETRO <span className="meta-line" /> <span>{message.time}</span></>}</div><p>{message.text}</p>{message.tags && <div className="tags">{message.tags.map(tag => <span key={tag}>{tag}</span>)}</div>}<span className="message-time">{message.time}</span></article>)}</div>
          <form className="composer" onSubmit={sendMessage}><div className="composer-top"><span className="prompt-symbol">›</span><input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Tell Retro what you want to make..." aria-label="Prompt Retro" /><button type="button" className="attach"><Paperclip /></button><button type="button" className="mic"><Mic /></button></div><div className="composer-bottom"><div><button type="button" className="utility"><Command />⌘K</button><button type="button" className="utility"><Paperclip /> Attach</button></div><div className="composer-actions"><span>SHIFT + ENTER FOR NEW LINE</span><button className="send-button" disabled={running || !input.trim()}>{running ? <Radio className="spin" /> : <Send />} {running ? 'RUNNING' : 'GENERATE'}</button></div></div></form>
        </div>
      </section>

      {rightOpen && <aside className="inspector"><div className="inspector-head"><div><p className="eyebrow">LIVE SYSTEM</p><h2>Control room</h2></div><button className="icon-btn" onClick={() => setRightOpen(false)}><X /></button></div><div className="signal-card"><div className="signal-header"><span><Cpu /> RETRO CORE</span><span className="online">ONLINE</span></div><div className="signal-visual"><div className="orb"><div className="orb-ring" /><span>R</span></div><div className="signal-copy"><b>Creative mode</b><small>Adaptive reasoning active</small><div className="wave"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div></div></div></div><div className="inspector-section"><div className="section-title"><span>OUTPUT QUEUE</span><button><Plus /></button></div><div className="queue-item"><span className="queue-status" /><div><b>Launch narrative</b><small>Writing · 34% complete</small></div><span className="queue-time">NOW</span></div><div className="queue-item muted"><span className="queue-status" /><div><b>Visual direction</b><small>Waiting for narrative</small></div><span className="queue-time">NEXT</span></div></div><div className="inspector-section controls"><div className="section-title"><span>ENVIRONMENT</span><Gauge /></div><label><span><Volume2 /> Volume</span><b>{volume}%</b><input type="range" value={volume} onChange={e => setVolume(Number(e.target.value))} /></label><label><span><Terminal /> Brightness</span><b>{brightness}%</b><input type="range" value={brightness} onChange={e => setBrightness(Number(e.target.value))} /></label></div><div className="inspector-footer"><button><FileCode2 /> View system log</button><button><Copy /> Copy session ID</button></div></aside>}
    </main>
  )
}
