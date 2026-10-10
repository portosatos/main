import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { AuthValues, loginSchema, registerSchema } from "@/lib/authSchemas";

type Props = {
  title: string;
  description: string;
  schema: typeof loginSchema | typeof registerSchema;
  passwordAutoComplete: "current-password" | "new-password";
  submitLabel: string;
  pending: boolean;
  serverError: string | null;
  onSubmit: (values: AuthValues) => void;
  footer: { text: string; linkLabel: string; to: string };
};

// The login and registration form: email and password, errors under the fields (SPEC F1).
export default function AuthForm(props: Props) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AuthValues>({
    resolver: zodResolver(props.schema),
    defaultValues: { email: "", password: "" },
  });

  return (
    <div className="flex min-h-screen items-start justify-center bg-background px-4 py-12 text-foreground sm:items-center">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <p className="text-sm text-muted-foreground">Трекер здоровья</p>
          <CardTitle>
            <h1 className="text-xl">{props.title}</h1>
          </CardTitle>
          <CardDescription>{props.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" noValidate onSubmit={handleSubmit(props.onSubmit)}>
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={errors.email ? "email-error" : undefined}
                {...register("email")}
              />
              {errors.email && (
                <p id="email-error" className="text-sm text-destructive">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                type="password"
                autoComplete={props.passwordAutoComplete}
                aria-invalid={errors.password ? true : undefined}
                aria-describedby={errors.password ? "password-error" : undefined}
                {...register("password")}
              />
              {errors.password && (
                <p id="password-error" className="text-sm text-destructive">
                  {errors.password.message}
                </p>
              )}
            </div>
            {props.serverError && (
              <p role="alert" className="text-sm text-destructive">
                {props.serverError}
              </p>
            )}
            <Button type="submit" disabled={props.pending}>
              {props.submitLabel}
            </Button>
          </form>
          <p className="mt-4 text-sm text-muted-foreground">
            {props.footer.text}{" "}
            <Link className="text-foreground underline underline-offset-4" to={props.footer.to}>
              {props.footer.linkLabel}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
