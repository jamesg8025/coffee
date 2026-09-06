'use client'

import Link from 'next/link'
import { useAuth } from '@/contexts/auth'
import { LogOut } from 'lucide-react'

const roleBadgeClasses: Record<string, string> = {
  ADMIN: 'bg-red-700 text-red-100',
  ROASTER: 'bg-amber-700 text-amber-100',
  CONSUMER: 'bg-stone-600 text-stone-100',
}

export default function Navbar() {
  const { user, isLoading, logout } = useAuth()

  return (
    <nav className="sticky top-0 z-50 bg-amber-950 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <Link
            href="/catalog"
            className="flex items-center gap-2 text-white font-semibold text-lg tracking-tight hover:text-amber-200 transition-colors"
          >
            <span>☕</span>
            <span>Coffee Connoisseur</span>
          </Link>

          <div className="flex items-center gap-4">
            {isLoading ? null : user ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-amber-200 text-sm hidden sm:block">
                    {user.email}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      roleBadgeClasses[user.role] ?? 'bg-stone-600 text-stone-100'
                    }`}
                  >
                    {user.role}
                  </span>
                </div>
                <button
                  onClick={() => void logout()}
                  className="flex items-center gap-1.5 text-amber-200 hover:text-white text-sm transition-colors"
                  aria-label="Logout"
                >
                  <LogOut className="w-4 h-4" />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="text-amber-200 hover:text-white text-sm transition-colors"
                >
                  Login
                </Link>
                <Link
                  href="/register"
                  className="bg-amber-700 hover:bg-amber-600 text-white text-sm px-3 py-1.5 rounded-lg transition-colors"
                >
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
