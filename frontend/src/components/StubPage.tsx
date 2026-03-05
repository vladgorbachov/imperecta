import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface StubPageProps {
  title: string;
}

export function StubPage({ title }: StubPageProps) {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-foreground">{title}</h1>
      <Card>
        <CardHeader>
          <CardTitle>{t("common.comingSoon")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            {t("common.underDevelopment")}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
