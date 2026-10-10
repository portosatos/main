import { useNavigate } from "react-router";

import { errorMessage, useRegister } from "@/api/auth";
import AuthForm from "@/components/AuthForm";
import { registerSchema } from "@/lib/authSchemas";

// Registration logs the user in right away (the API sets the session cookie).
export default function Register() {
  const registration = useRegister();
  const navigate = useNavigate();

  return (
    <AuthForm
      title="Регистрация"
      description="Часовой пояс возьмём из браузера, его можно будет поменять в настройках."
      schema={registerSchema}
      passwordAutoComplete="new-password"
      submitLabel="Зарегистрироваться"
      pending={registration.isPending}
      serverError={
        registration.isError
          ? errorMessage(registration.error, "Не удалось зарегистрироваться")
          : null
      }
      onSubmit={(values) =>
        registration.mutate(values, { onSuccess: () => navigate("/", { replace: true }) })
      }
      footer={{ text: "Уже есть аккаунт?", linkLabel: "Войти", to: "/login" }}
    />
  );
}
