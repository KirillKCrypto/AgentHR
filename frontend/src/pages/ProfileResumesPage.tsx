import { Link } from 'react-router'

import { ResumeHistoryCard } from '@/components/ResumeHistoryCard'
import { ResumeUploadCard } from '@/components/ResumeUploadCard'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useAuthToken } from '@/lib/useAuthToken'

export default function ProfileResumesPage() {
  const { token, expire } = useAuthToken()

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Резюме</CardTitle>
          <CardDescription>Войдите, чтобы загрузить резюме.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <ResumeUploadCard token={token} onUnauthorized={expire} />
      <ResumeHistoryCard token={token} onUnauthorized={expire} />
    </div>
  )
}
