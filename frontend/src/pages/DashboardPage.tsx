import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function DashboardPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Дашборд</CardTitle>
        <CardDescription>
          Здесь появятся вакансии, активный план подготовки и последние интервью.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-muted-foreground">
        Каркас интерфейса готов: роутинг, Tailwind CSS и компоненты shadcn/ui. Наполнение —
        по плану недель 2–7.
      </CardContent>
    </Card>
  )
}
