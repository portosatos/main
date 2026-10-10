import { useLocation, useNavigate } from "react-router";

import { errorMessage, useLogin } from "@/api/auth";
import AuthForm from "@/components/AuthForm";
import { loginSchema } from "@/lib/authSchemas";

// After login the user returns to the page ProtectedRoute sent them away from, or to "/".
export default function Login() {
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  return (
    <AuthForm
      title="Вход"
      description="Войдите, чтобы увидеть свои данные."
      schema={loginSchema}
      passwordAutoComplete="current-password"
      submitLabel="Войти"
      pending={login.isPending}
      serverError={login.isError ? errorMessage(login.error, "Не удалось войти") : null}
      onSubmit={(values) =>
        login.mutate(values, { onSuccess: () => navigate(from, { replace: true }) })
      }
      footer={{ text: "Нет аккаунта?", linkLabel: "Зарегистрироваться", to: "/register" }}
    />
  );
}
