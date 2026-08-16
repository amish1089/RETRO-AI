import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Retro AI — Creative Operating System',
  description: 'A next-generation creative workspace for making unexpected things with Retro AI.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className="bg-[#080c10]"><body>{children}</body></html>
}
