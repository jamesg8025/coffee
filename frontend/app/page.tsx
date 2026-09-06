'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/auth'

export default function RootPage() {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (isLoading) return
    if (user) {
      router.replace('/catalog')
    } else {
      router.replace('/login')
    }
  }, [user, isLoading, router])

  return null
}
