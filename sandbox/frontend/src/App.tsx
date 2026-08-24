import { useEffect, useState } from 'react'
import { ApiError } from '@/errors.ts'

interface Info {
  app_name: string
  admin_email: string
  items_per_user: number
}

export default function App() {
  const [info, setInfo] = useState<Info | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    fetch('/api/info')
      .then((res) => {
        if (!res.ok) throw ApiError.fromResponse(res)
        return res.json() as Promise<Info>
      })
      .then(setInfo)
      .catch((e: ApiError) => setError(e))
  }, [])

  return (
    <main>
      <h1>Fast API Standard</h1>
      {error && <p role="alert">Error: {error.message}</p>}
      {info && (
        <dl>
          <dt>App name</dt>
          <dd>{info.app_name}</dd>
          <dt>Admin email</dt>
          <dd>{info.admin_email}</dd>
          <dt>Items per user</dt>
          <dd>{info.items_per_user}</dd>
        </dl>
      )}
      {!info && !error && <p>Loading…</p>}
    </main>
  )
}
