import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// App shell: header and main area. Pages and routing come with later steps.
export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center px-4 py-3">
          <h1 className="text-lg font-semibold">Трекер здоровья</h1>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Card>
          <CardHeader>
            <CardTitle>Скелет приложения</CardTitle>
            <CardDescription>Страницы появятся на следующих шагах.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <a href="/api/health">Состояние API</a>
            </Button>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
