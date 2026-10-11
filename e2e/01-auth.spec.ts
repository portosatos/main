import { PASSWORD, uniqueEmail } from "./lib/users";
import { expect, test } from "./test";

// SPEC §8 stage 12, scenario 1: registration, login, logout (F1).

test("регистрация, вход и выход", async ({ page }) => {
  const email = uniqueEmail("auth");
  const header = page.getByRole("banner");

  // Without a session the app sends the user to the login page.
  await page.goto("/upload");
  await expect(page).toHaveURL(/\/login$/);

  // React Router renders a navigation in a transition: the URL changes before the new form is
  // mounted, so the fields are filled only once the page's heading is there.
  await page.getByRole("link", { name: "Зарегистрироваться" }).click();
  await expect(page).toHaveURL(/\/register$/);
  await expect(page.getByRole("heading", { name: "Регистрация" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill(PASSWORD);
  await page.getByRole("button", { name: "Зарегистрироваться" }).click();

  // Registration logs the user in right away.
  await expect(page).toHaveURL(/\/$/);
  await expect(header).toContainText(email);
  await expect(page.getByRole("heading", { name: "Дашборд" })).toBeVisible();

  // The session survives a reload (cookie).
  await page.reload();
  await expect(header).toContainText(email);

  await header.getByRole("button", { name: "Выйти" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/upload");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Вход" })).toBeVisible();

  // A wrong password is refused with a message, the right one lets the user in.
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill(`${PASSWORD}-wrong`);
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Пароль").fill(PASSWORD);
  await page.getByRole("button", { name: "Войти" }).click();
  // Back to the page the user was sent away from.
  await expect(page).toHaveURL(/\/upload$/);
  await expect(header).toContainText(email);
  await expect(page.getByRole("heading", { name: "Загрузка", exact: true })).toBeVisible();
});
