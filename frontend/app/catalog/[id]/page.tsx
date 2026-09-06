'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, MapPin, BookmarkPlus } from 'lucide-react'
import { coffeeFetch } from '@/lib/api'
import { Coffee, RoastLevel } from '@/lib/types'
import { useAuth } from '@/contexts/auth'

const roastLabels: Record<RoastLevel, string> = {
  light: 'Light',
  medium: 'Medium',
  medium_dark: 'Medium Dark',
  dark: 'Dark',
}

const roastBadgeClasses: Record<RoastLevel, string> = {
  light: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  medium: 'bg-orange-100 text-orange-800 border border-orange-200',
  medium_dark: 'bg-red-100 text-red-800 border border-red-200',
  dark: 'bg-stone-200 text-stone-700 border border-stone-300',
}

async function fetchCoffee(id: string): Promise<Coffee> {
  const res = await coffeeFetch(`/coffees/${id}`)
  if (!res.ok) {
    if (res.status === 404) throw new Error('Coffee not found')
    throw new Error('Failed to fetch coffee details')
  }
  return res.json() as Promise<Coffee>
}

export default function CoffeeDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { user } = useAuth()
  const id = typeof params.id === 'string' ? params.id : ''

  const { data: coffee, isLoading, isError, error } = useQuery({
    queryKey: ['coffee', id],
    queryFn: () => fetchCoffee(id),
    enabled: Boolean(id),
  })

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse">
          <div className="h-4 bg-stone-200 rounded w-24 mb-8" />
          <div className="bg-white rounded-xl border border-stone-200 p-8 space-y-4">
            <div className="h-8 bg-stone-200 rounded w-2/3" />
            <div className="h-4 bg-stone-200 rounded w-1/4" />
            <div className="h-4 bg-stone-200 rounded w-1/3" />
            <div className="space-y-2 pt-4">
              <div className="h-3 bg-stone-200 rounded w-full" />
              <div className="h-3 bg-stone-200 rounded w-5/6" />
              <div className="h-3 bg-stone-200 rounded w-4/6" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (isError || !coffee) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-stone-500 hover:text-stone-800 text-sm mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-stone-500 text-lg font-medium">
            {error instanceof Error ? error.message : 'Something went wrong'}
          </p>
        </div>
      </div>
    )
  }

  const flavorEntries = coffee.flavor_profile
    ? Object.entries(coffee.flavor_profile)
    : []

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <button
        onClick={() => router.push('/catalog')}
        className="flex items-center gap-1.5 text-stone-500 hover:text-stone-800 text-sm mb-8 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to catalog
      </button>

      <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-8">
        <div className="flex flex-wrap items-start gap-3 mb-4">
          <h1 className="text-3xl font-bold text-stone-900 flex-1">{coffee.name}</h1>
          {coffee.roast_level && (
            <span
              className={`rounded-full px-3 py-1 text-sm font-medium ${
                roastBadgeClasses[coffee.roast_level]
              }`}
            >
              {roastLabels[coffee.roast_level]} Roast
            </span>
          )}
        </div>

        {coffee.origin_country && (
          <div className="flex items-center gap-2 text-stone-500 mb-6">
            <MapPin className="w-4 h-4 shrink-0" />
            <span>{coffee.origin_country}</span>
          </div>
        )}

        {coffee.description && (
          <div className="mb-6">
            <h2 className="text-sm font-semibold text-stone-700 uppercase tracking-wide mb-2">
              About
            </h2>
            <p className="text-stone-600 leading-relaxed">{coffee.description}</p>
          </div>
        )}

        {flavorEntries.length > 0 && (
          <div className="mb-6">
            <h2 className="text-sm font-semibold text-stone-700 uppercase tracking-wide mb-3">
              Flavor Profile
            </h2>
            <div className="flex flex-wrap gap-2">
              {flavorEntries.map(([key, value]) => (
                <span
                  key={key}
                  className="bg-amber-50 text-amber-800 text-sm px-3 py-1 rounded-full border border-amber-200"
                >
                  {value !== null && value !== true && value !== ''
                    ? `${key}: ${String(value)}`
                    : key}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="border-t border-stone-100 pt-6 mt-2">
          <div className="flex flex-wrap items-center gap-4">
            {user && (
              <button
                onClick={() => router.push('/collection')}
                className="flex items-center gap-2 bg-amber-950 hover:bg-amber-900 text-white font-medium px-4 py-2.5 rounded-lg transition-colors text-sm"
              >
                <BookmarkPlus className="w-4 h-4" />
                Add to Collection
              </button>
            )}
            <span className="text-xs text-stone-400">
              Added {new Date(coffee.created_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
