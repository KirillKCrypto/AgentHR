import { Link } from 'react-router'

import { PlanSkillTestsCard } from '@/components/PlanSkillTestsCard'
import { buttonVariants } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useAuthToken } from '@/lib/useAuthToken'

export default function ProfileTestsPage() {
  const { token, expire } = useAuthToken()

  if (token === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Тесты</CardTitle>
          <CardDescription>Войдите, чтобы пройти тесты.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login" className={buttonVariants()}>
            Войти
          </Link>
        </CardContent>
      </Card>
    )
  }

  return <PlanSkillTestsCard token={token} onUnauthorized={expire} />
}
