export function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md rounded-lg border p-8">
        <h1 className="mb-6 text-2xl font-bold">Вход</h1>
        <form className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            className="w-full rounded-md border px-3 py-2"
          />
          <input
            type="password"
            placeholder="Пароль"
            className="w-full rounded-md border px-3 py-2"
          />
          <button
            type="submit"
            className="w-full rounded-md bg-primary py-2 text-primary-foreground"
          >
            Войти
          </button>
        </form>
      </div>
    </div>
  );
}
