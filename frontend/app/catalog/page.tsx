'use client'

import { useMemo, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { coffeeFetch } from '@/lib/api'
import { Coffee, RoastLevel } from '@/lib/types'
import CoffeeCard from '@/components/CoffeeCard'

type RoastFilter = RoastLevel | 'all'

const roastFilters: { label: string; value: RoastFilter }[] = [
  { label: 'All', value: 'all' },
  { label: 'Light', value: 'light' },
  { label: 'Medium', value: 'medium' },
  { label: 'Medium Dark', value: 'medium_dark' },
  { label: 'Dark', value: 'dark' },
]

async function fetchCoffees(): Promise<Coffee[]> {
  const res = await coffeeFetch('/coffees')
  if (!res.ok) throw new Error('Failed to fetch coffees')
  return res.json() as Promise<Coffee[]>
}

function CoffeeCardSkeleton() {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-5 animate-pulse">
      <div className="flex justify-between mb-3">
        <div className="h-4 bg-stone-200 rounded w-3/5" />
        <div className="h-4 bg-stone-200 rounded w-1/5" />
      </div>
      <div className="h-3 bg-stone-200 rounded w-2/5 mb-3" />
      <div className="space-y-2">
        <div className="h-3 bg-stone-200 rounded w-full" />
        <div className="h-3 bg-stone-200 rounded w-4/5" />
      </div>
    </div>
  )
}

export default function CatalogPage() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const search = searchParams.get('q') ?? ''
  const roastFilter = (searchParams.get('roast') ?? 'all') as RoastFilter

  const setSearch = useCallback(
    (value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value) params.set('q', value)
      else params.delete('q')
      router.replace(`/catalog?${params.toString()}`, { scroll: false })
    },
    [router, searchParams]
  )

  const setRoastFilter = useCallback(
    (value: RoastFilter) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value !== 'all') params.set('roast', value)
      else params.delete('roast')
      router.replace(`/catalog?${params.toString()}`, { scroll: false })
    },
    [router, searchParams]
  )

  const { data: coffees, isLoading, isError, error } = useQuery({
    queryKey: ['coffees'],
    queryFn: fetchCoffees,
  })

  const filtered = useMemo(() => {
    if (!coffees) return []
    let result = coffees

    if (roastFilter !== 'all') {
      result = result.filter((c) => c.roast_level === roastFilter)
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase()
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.origin_country?.toLowerCase().includes(q) ?? false)
      )
    }

    return result
  }, [coffees, search, roastFilter])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-stone-900 mb-1">Coffee Catalog</h1>
        <p className="text-stone-500">
          Explore exceptional coffees from around the world
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or origin…"
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-stone-300 text-stone-900 text-sm placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition bg-white"
          />
        </div>

        <div className="flex gap-2 flex-wrap">
          {roastFilters.map((f) => (
            <button
              key={f.value}
              onClick={() => setRoastFilter(f.value)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                roastFilter === f.value
                  ? 'bg-amber-950 text-white'
                  : 'bg-white text-stone-600 border border-stone-300 hover:border-amber-400 hover:text-amber-800'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <CoffeeCardSkeleton key={i} />
          ))}
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-stone-500 text-lg font-medium">
            Unable to load coffees
          </p>
          <p className="text-stone-400 text-sm mt-1">
            {error instanceof Error ? error.message : 'An unexpected error occurred'}
          </p>
        </div>
      )}

      {!isLoading && !isError && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <span className="text-5xl mb-4">☕</span>
          <p className="text-stone-500 text-lg font-medium">No coffees found</p>
          <p className="text-stone-400 text-sm mt-1">
            {search || roastFilter !== 'all'
              ? 'Try adjusting your search or filters'
              : 'No coffees have been added yet'}
          </p>
        </div>
      )}

      {!isLoading && !isError && filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((coffee) => (
            <CoffeeCard key={coffee.id} coffee={coffee} />
          ))}
        </div>
      )}
    </div>
  )
}
