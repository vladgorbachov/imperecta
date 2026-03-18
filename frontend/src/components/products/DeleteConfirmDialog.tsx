/**
 * Confirmation dialog before bulk delete.
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface DeleteConfirmDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  count: number;
  isLoading: boolean;
}

export function DeleteConfirmDialog({
  open,
  onConfirm,
  onCancel,
  count,
  isLoading,
}: DeleteConfirmDialogProps) {
  const label =
    count === 1
      ? "1 товар"
      : count < 5
        ? `${count} товара`
        : `${count} товаров`;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Удалить товары?</DialogTitle>
          <DialogDescription>
            Вы собираетесь удалить {label}. Это действие нельзя отменить.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={isLoading}>
            Отмена
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isLoading}>
            {isLoading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              "Удалить"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
