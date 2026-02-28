import Link from 'next/link'
import { Activity, Database, Settings, Terminal, CheckCircle, FileText, ScrollText } from 'lucide-react'

export function Sidebar() {
  const links = [
    { name: 'Chat Console', href: '/', icon: Terminal },
    { name: 'Model Manager', href: '/models', icon: Database },
    { name: 'Documents (RAG)', href: '/documents', icon: FileText },
    { name: 'System Metrics', href: '/system', icon: Activity },
    { name: 'Benchmark', href: '/benchmark', icon: CheckCircle },
    { name: 'System Logs', href: '/logs', icon: ScrollText },
    { name: 'Settings', href: '/settings', icon: Settings },
  ]

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 text-slate-300 flex flex-col h-full">
      <div className="p-4 uppercase text-xs font-semibold text-slate-500 tracking-wider">
        Navigation
      </div>
      <nav className="flex-1 px-2 space-y-1">
        {links.map((link) => (
          <Link
            key={link.name}
            href={link.href}
            className="flex items-center px-3 py-2 text-sm font-medium rounded-md hover:bg-slate-800 hover:text-white transition-colors group"
          >
            <link.icon className="mr-3 h-5 w-5 flex-shrink-0 text-slate-400 group-hover:text-blue-500" />
            {link.name}
          </Link>
        ))}
      </nav>
    </div>
  )
}
