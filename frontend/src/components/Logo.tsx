'use client'

import Image from 'next/image'

export function Logo({ variant = 'full', className = '' }: { variant?: 'full' | 'icon'; className?: string }) {
  if (variant === 'icon') {
    return (
      <div className={`relative ${className}`}>
        <Image
          src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQLTeL1JS8uV9vNZ_lPRd54BKY8c_D498w7PQ&s"
          alt="Logo"
          width={36}
          height={36}
          className="rounded"
        />
      </div>
    )
  }

  return (
    <div className={`relative ${className}`}>
      <Image
        src="https://newwavesolution.com/wp-content/uploads/2025/07/logo-nws.svg"
        alt="NewWave Solutions"
        width={136}
        height={36}
        priority
      />
    </div>
  )
}

