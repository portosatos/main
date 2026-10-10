import { render, screen } from "@testing-library/react";

import App from "./App";

test.fails("renders app shell with title «Трекер здоровья»", () => {
  render(<App />);

  expect(screen.getByRole("banner")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Трекер здоровья" })).toBeInTheDocument();
});
