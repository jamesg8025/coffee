'use client'

import Link from 'next/link'
import { MapPin } from 'lucide-react'
import { Coffee, RoastLevel } from '@/lib/types'

const roastBadgeClasses: Record<RoastLevel, string> = {
  light: 'bg-yellow-100 text-yellow-800',
  medium: 'bg-orange-100 text-orange-800',
  medium_dark: 'bg-red-100 text-red-800',
  dark: 'bg-stone-200 text-stone-700',
}

const roastLabels: Record<RoastLevel, string> = {
  light: 'Light',
  medium: 'Medium',
  medium_dark: 'Medium Dark',
  dark: 'Dark',
}

interface CoffeeCardProps {
  coffee: Coffee
}

export default function CoffeeCard({ coffee }: CoffeeCardProps) {
  const flavorKeys =
    coffee.flavor_profile
      ? Object.keys(coffee.flavor_profile).slice(0, 5)
      : []

  return (
    <Link href={`/catalog/${coffee.id}`} className="group block">
      <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-5 h-full flex flex-col gap-3 hover:shadow-md hover:border-amber-300 transition-all duration-200">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-stone-900 text-base leading-snug group-hover:text-amber-800 transition-colors">
            {coffee.name}
          </h3>
          {coffee.roast_level && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium shrink-0 ${
                roastBadgeClasses[coffee.roast_level]
              }`}
            >
              {roastLabels[coffee.roast_level]}
            </span>
          )}
        </div>

        {coffee.origin_country && (
          <div className="flex items-center gap-1.5 text-stone-500 text-sm">
            <MapPin className="w-3.5 h-3.5 shrink-0" />
            <span>{coffee.origin_country}</span>
          </div>
        )}

        {coffee.description && (
          <p className="text-stone-600 text-sm leading-relaxed line-clamp-2 flex-1">
            {coffee.description}
          </p>
        )}

        {flavorKeys.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-auto pt-1">
            {flavorKeys.map((key) => (
              <span
                key={key}
                className="bg-amber-50 text-amber-800 text-xs px-2 py-0.5 rounded-full border border-amber-200"
              >
                {key}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  )
}
