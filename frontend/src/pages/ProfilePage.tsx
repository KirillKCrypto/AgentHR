import { NavLink, Outlet } from 'react-router'

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/profile', label: 'Обзор', end: true },
  { to: '/profile/resumes', label: 'Резюме' },
  { to: '/profile/skills', label: 'Навыки' },
  { to: '/profile/tests', label: 'Тесты' },
]

function tabClass({ isActive }: { isActive: boolean }): string {
  return cn(
    'rounded-md px-3 py-1.5 text-sm transition-colors',
    isActive
      ? 'bg-primary text-primary-foreground'
      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
  )
}

export default function ProfilePage() {
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Профиль</CardTitle>
          <CardDescription>
            Резюме, навыки и тесты разделены по разделам, чтобы не теряться в объёме.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <nav className="flex flex-wrap gap-2">
            {TABS.map((tab) => (
              <NavLink key={tab.to} to={tab.to} end={tab.end} className={tabClass}>
                {tab.label}
              </NavLink>
            ))}
          </nav>
        </CardContent>
      </Card>
      <Outlet />
    </div>
  )
}
