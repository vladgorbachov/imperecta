/**
 * Legal guard for the protected list (EU/EEA, GB, CH, MD, UA): Regulation
 * (EU) 2018/302 forbids geo-blocking inside the single market, so blocking
 * one of these needs an explicit basis note and `force: true`. Never a
 * one-click bypass — the note is mandatory and lands in the audit log.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { flagForCode } from "@/lib/countryFlag";

export interface ProtectedCountryWarningProps {
  open: boolean;
  countryCode: string;
  countryName: string;
  pending?: boolean;
  onCancel: () => void;
  /** Called with the mandatory note; the caller resubmits with `force: true`. */
  onConfirm: (note: string) => void;
}

export function ProtectedCountryWarning({
  open,
  countryCode,
  countryName,
  pending = false,
  onCancel,
  onConfirm,
}: ProtectedCountryWarningProps) {
  const { t } = useTranslation();
  const [note, setNote] = useState("");
  const noteValid = note.trim().length >= 10;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setNote("");
          onCancel();
        }
      }}
    >
      <DialogContent className="surface-overlay sm:max-w-lg" data-testid="protected-country-warning">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlert className="size-4 text-[var(--status-warn)]" />
            {t("admin.compliance.protected.title")}
          </DialogTitle>
          <DialogDescription>
            <span aria-hidden>{flagForCode(countryCode)}</span> {countryName} ({countryCode})
          </DialogDescription>
        </DialogHeader>
        <p className="rounded-md border border-[var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-sm leading-relaxed">
          {t("admin.compliance.protectedWarning")}
        </p>
        <div className="space-y-1.5">
          <label className="label-mono block" htmlFor="protected-note">
            {t("admin.compliance.protected.noteLabel")}
          </label>
          <Input
            id="protected-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={t("admin.compliance.protected.notePlaceholder")}
          />
          {!noteValid ? (
            <p className="text-xs text-muted-foreground">
              {t("admin.compliance.protected.noteRequired")}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={pending}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="destructive"
            disabled={!noteValid || pending}
            onClick={() => onConfirm(note.trim())}
          >
            {t("admin.compliance.protected.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
