import { Link } from 'react-router'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <p className="text-4xl font-semibold">404</p>
      <p className="text-muted-foreground">Страница не найдена.</p>
      <Link to="/" className="text-sm underline underline-offset-4">
        Вернуться на главную
      </Link>
    </div>
  )
}
