export function CompetitorPricesTable() {
  return (
    <div className="rounded-lg border">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="p-4 text-left">Конкурент</th>
            <th className="p-4 text-left">Цена</th>
            <th className="p-4 text-left">Статус</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={3} className="p-8 text-center text-muted-foreground">
              Нет данных
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
