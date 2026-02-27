import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Fuja do Mico — Dashboard',
  description: 'Painel operacional da newsletter Liga HUB Finance',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-white text-gray-900">
        {/* Navbar */}
        <nav className="border-b border-gray-200 px-6 py-3 flex items-center gap-6">
          <a href="/" className="font-bold text-lg text-gray-900 hover:text-gray-600">
            Fuja do Mico
          </a>
          <a href="/" className="text-sm text-gray-500 hover:text-gray-900">
            Edições
          </a>
          <a href="/chat" className="text-sm text-gray-500 hover:text-gray-900">
            Chat IA
          </a>
        </nav>

        <main className="px-6 py-6">
          {children}
        </main>
      </body>
    </html>
  )
}
