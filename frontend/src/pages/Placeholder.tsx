import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// An empty section of the menu (SPEC §6.4): its page comes with a later step.
export default function Placeholder({ title }: { title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>{title}</h2>
        </CardTitle>
        <CardDescription>Раздел появится на следующих шагах.</CardDescription>
      </CardHeader>
    </Card>
  );
}
