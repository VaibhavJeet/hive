'use client'

import CivilizationMap from '@/components/CivilizationMap'

export default function WorldPage() {
  return (
    <div className="fixed inset-0 bg-[#0a0a0a]" style={{ marginLeft: '48px' }}>
      <CivilizationMap />
    </div>
  )
}
