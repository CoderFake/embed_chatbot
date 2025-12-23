import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PUBLIC_ROUTES = ['/login', '/change-password', '/accept-invite', '/forgot-password', '/reset-password']
const AUTH_ROUTES = ['/login', '/accept-invite']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  const accessToken = request.cookies.get('access_token')?.value ||
    request.headers.get('authorization')?.replace('Bearer ', '')

  const isPublicRoute = PUBLIC_ROUTES.some(route => pathname.startsWith(route))
  const isAuthRoute = AUTH_ROUTES.some(route => pathname.startsWith(route))

  if (pathname === '/') {
    if (accessToken) {
      return NextResponse.redirect(new URL('/dashboard', request.url))
    }
    return NextResponse.redirect(new URL('/login', request.url))
  }

  if (pathname.startsWith('/change-password') && accessToken) {
    return NextResponse.next()
  }

  if (isAuthRoute && accessToken) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  if (!isPublicRoute && !accessToken) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\..*|public).*)',
  ],
}

