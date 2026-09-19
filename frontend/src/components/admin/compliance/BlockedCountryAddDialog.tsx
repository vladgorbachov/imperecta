/**
 * Add (with impact preview) or edit a blocked country.
 * Add flow: pick from the full ISO list → reason/basis/note → dry-run shows
 * affected users/marketplaces → save only when no active marketplaces remain.
 * A 409 protected_country on either step opens ProtectedCountryWarning; the
 * step is retried with `force: true` and the mandatory note.
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { AlertTriangle, Check, Search } from "lucide-react";
import type {
  AvailableCountry,
  BlockedCountry,
  BlockedCountryDryRunResult,
  BlockedReason,
} from "@/api/admin";
import {
  useAddBlockedCountry,
  useAvailableCountries,
  useDryRunBlockedCountry,
  useUpdateBlockedCountry,
} from "@/hooks/useAdmin";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ProtectedCountryWarning } from "@/components/admin/compliance/ProtectedCountryWarning";
import {
  describeDetail,
  errorDetail,
  isProtectedCountryError,
} from "@/components/admin/compliance/complianceErrors";
import {
  REASON_LABELS,
  REASON_ORDER,
} from "@/components/admin/compliance/reasonBadge";
import { flagForCode } from "@/lib/countryFlag";
import { cn } from "@/lib/utils";

export interface BlockedCountryAddDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When set the dialog edits this row (no picker, no dry-run). */
  editing?: BlockedCountry | null;
}

type PendingStep = "preview" | "save" | null;

const PICKER_LIMIT = 40;

export function BlockedCountryAddDialog({
  open,
  onOpenChange,
  editing = null,
}: BlockedCountryAddDialogProps) {
  const { t } = useTranslation();
  const isEdit = editing != null;

  const { data: available, isLoading: availableLoading } = useAvailableCountries(
    open && !isEdit,
  );
  const dryRun = useDryRunBlockedCountry();
  const addCountry = useAddBlockedCountry();
  const updateCountry = useUpdateBlockedCountry();

  const [countryQuery, setCountryQuery] = useState("");
  const [selected, setSelected] = useState<AvailableCountry | null>(null);
  const [reason, setReason] = useState<BlockedReason>("comprehensive_sanctions");
  const [basis, setBasis] = useState("");
  const [note, setNote] = useState("");
  const [reviewDue, setReviewDue] = useState("");
  const [impact, setImpact] = useState<BlockedCountryDryRunResult | null>(null);
  const [impactFor, setImpactFor] = useState<string | null>(null);
  const [forceNote, setForceNote] = useState<string | null>(null);
  const [pendingStep, setPendingStep] = useState<PendingStep>(null);

  /* Edit mode seeds the form from the row each time the dialog opens. */
  useEffect(() => {
    if (!open) {
      return;
    }
    if (editing) {
      setReason(editing.reason);
      setBasis(editing.basis);
      setNote(editing.note ?? "");
      setReviewDue(editing.review_due_at.slice(0, 10));
    }
  }, [open, editing]);

  const reset = () => {
    setCountryQuery("");
    setSelected(null);
    setReason("comprehensive_sanctions");
    setBasis("");
    setNote("");
    setReviewDue("");
    setImpact(null);
    setImpactFor(null);
    setForceNote(null);
    setPendingStep(null);
  };

  const pickerRows = useMemo(() => {
    const query = countryQuery.trim().toLowerCase();
    const rows = (available ?? []).filter(
      (row) =>
        !query ||
        row.code.toLowerCase().includes(query) ||
        row.name.toLowerCase().includes(query),
    );
    return rows.slice(0, PICKER_LIMIT);
  }, [available, countryQuery]);

  const countryCode = isEdit ? editing.country_code : selected?.code ?? null;
  const countryName = isEdit ? editing.name : selected?.name ?? "";
  const basisValid = basis.trim().length > 0;
  const formValid = countryCode != null && basisValid;
  const impactCurrent = impact != null && impactFor === countryCode;
  const marketplacesBlock = impactCurrent && impact.affected_marketplaces > 0;
  const canSave = isEdit ? basisValid : formValid && impactCurrent && !marketplacesBlock;
  const busy = dryRun.isPending || addCountry.isPending || updateCountry.isPending;

  /* The protected-country note is passed explicitly: state set in the same
     tick would still be stale inside these closures. */
  const composedNote = (extraNote: string | null): string | null => {
    const parts = [note.trim(), extraNote?.trim() ?? ""].filter(Boolean);
    return parts.length > 0 ? parts.join(" — ") : null;
  };

  const runPreview = async (force: boolean, extraNote: string | null = forceNote) => {
    if (!countryCode) {
      return;
    }
    try {
      const result = await dryRun.mutateAsync({
        country_code: countryCode,
        reason,
        basis: basis.trim(),
        note: composedNote(extraNote),
        force,
      });
      setImpact(result);
      setImpactFor(countryCode);
    } catch (error) {
      if (isProtectedCountryError(error)) {
        setPendingStep("preview");
        return;
      }
      toast.error(
        describeDetail(errorDetail(error), t("admin.compliance.errors.generic")),
      );
    }
  };

  const runSave = async (force: boolean, extraNote: string | null = forceNote) => {
    if (!countryCode) {
      return;
    }
    try {
      await addCountry.mutateAsync({
        country_code: countryCode,
        reason,
        basis: basis.trim(),
        note: composedNote(extraNote),
        force,
      });
      toast.success(t("admin.compliance.add.success", { country: countryName }));
      reset();
      onOpenChange(false);
    } catch (error) {
      if (isProtectedCountryError(error)) {
        setPendingStep("save");
        return;
      }
      toast.error(
        describeDetail(errorDetail(error), t("admin.compliance.errors.generic")),
      );
    }
  };

  const runUpdate = async () => {
    if (!editing) {
      return;
    }
    try {
      await updateCountry.mutateAsync({
        code: editing.country_code,
        payload: {
          reason,
          basis: basis.trim(),
          note: note.trim() || null,
          ...(reviewDue ? { review_due_at: reviewDue } : {}),
        },
      });
      toast.success(t("admin.compliance.edit.success", { country: editing.name }));
      reset();
      onOpenChange(false);
    } catch (error) {
      toast.error(
        describeDetail(errorDetail(error), t("admin.compliance.errors.generic")),
      );
    }
  };

  const onProtectedConfirm = (protectedNote: string) => {
    const step = pendingStep;
    setForceNote(protectedNote);
    setPendingStep(null);
    if (step === "preview") {
      void runPreview(true, protectedNote);
    } else if (step === "save") {
      void runSave(true, protectedNote);
    }
  };

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!next) {
            reset();
          }
          onOpenChange(next);
        }}
      >
        <DialogContent className="surface-overlay sm:max-w-lg" data-testid="blocked-country-dialog">
          <DialogHeader>
            <DialogTitle>
              {isEdit
                ? t("admin.compliance.edit.title", { country: editing.name })
                : t("admin.compliance.add.title")}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3">
            {/* Country */}
            <div className="space-y-1.5">
              <label className="label-mono block">{t("admin.compliance.add.country")}</label>
              {countryCode ? (
                <div className="flex items-center gap-2 rounded-md border border-[var(--accent-border)] bg-[var(--accent-bg-subtle)] px-3 py-2 text-sm">
                  <Check className="size-3.5 shrink-0 text-[var(--accent)]" />
                  <span aria-hidden>{flagForCode(countryCode)}</span>
                  <span className="min-w-0 flex-1 truncate">
                    {countryName} · <span className="font-mono">{countryCode}</span>
                  </span>
                  {selected?.is_protected ? (
                    <AlertTriangle
                      className="size-3.5 shrink-0 text-[var(--status-warn)]"
                      aria-label={t("admin.compliance.add.protectedHint")}
                    />
                  ) : null}
                  {!isEdit ? (
                    <button
                      type="button"
                      className="shrink-0 text-xs text-muted-foreground hover:text-[var(--foreground)]"
                      onClick={() => {
                        setSelected(null);
                        setImpact(null);
                        setImpactFor(null);
                      }}
                    >
                      {t("common.edit")}
                    </button>
                  ) : null}
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={countryQuery}
                      onChange={(event) => setCountryQuery(event.target.value)}
                      placeholder={t("admin.compliance.add.countrySearch")}
                      className="pl-8"
                      autoFocus
                      data-testid="country-picker-search"
                    />
                  </div>
                  <div className="max-h-48 overflow-y-auto rounded-md border border-[var(--glass-border)]">
                    {availableLoading ? (
                      <p className="px-3 py-2 text-sm text-muted-foreground">
                        {t("common.loading")}
                      </p>
                    ) : pickerRows.length === 0 ? (
                      <p className="px-3 py-2 text-sm text-muted-foreground">
                        {t("admin.compliance.add.noMatch")}
                      </p>
                    ) : (
                      pickerRows.map((row) => (
                        <button
                          key={row.code}
                          type="button"
                          disabled={row.is_blocked}
                          className={cn(
                            "flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-[var(--glass-bg-hover)]",
                            row.is_blocked && "cursor-not-allowed opacity-50 hover:bg-transparent",
                          )}
                          onClick={() => {
                            setSelected(row);
                            setCountryQuery("");
                          }}
                        >
                          <span aria-hidden>{flagForCode(row.code)}</span>
                          <span className="w-8 shrink-0 font-mono text-xs text-muted-foreground">
                            {row.code}
                          </span>
                          <span className="min-w-0 flex-1 truncate">{row.name}</span>
                          {row.is_blocked ? (
                            <span className="label-mono shrink-0">
                              {t("admin.compliance.add.alreadyBlocked")}
                            </span>
                          ) : null}
                          {row.is_protected ? (
                            <AlertTriangle
                              className="size-3.5 shrink-0 text-[var(--status-warn)]"
                              aria-label={t("admin.compliance.add.protectedHint")}
                            />
                          ) : null}
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Reason + basis */}
            <div className="space-y-1.5">
              <label className="label-mono block">{t("admin.compliance.add.reason")}</label>
              <Select value={reason} onValueChange={(value) => setReason(value as BlockedReason)}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REASON_ORDER.map((value) => (
                    <SelectItem key={value} value={value}>
                      {t(REASON_LABELS[value])}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="label-mono block" htmlFor="blocked-basis">
                {t("admin.compliance.add.basis")}
              </label>
              <Input
                id="blocked-basis"
                value={basis}
                onChange={(event) => setBasis(event.target.value)}
                placeholder={t("admin.compliance.add.basisPlaceholder")}
                className={cn(!basisValid && basis !== "" && "border-[var(--status-error-border)]")}
              />
            </div>
            <div className="space-y-1.5">
              <label className="label-mono block" htmlFor="blocked-note">
                {t("admin.compliance.add.note")}
              </label>
              <Input
                id="blocked-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </div>
            {isEdit ? (
              <div className="space-y-1.5">
                <label className="label-mono block" htmlFor="blocked-review-due">
                  {t("admin.compliance.edit.reviewDue")}
                </label>
                <Input
                  id="blocked-review-due"
                  type="date"
                  value={reviewDue}
                  onChange={(event) => setReviewDue(event.target.value)}
                />
              </div>
            ) : null}

            {/* Impact preview (add mode) */}
            {!isEdit ? (
              <div className="space-y-2 rounded-md border border-[var(--glass-border)] p-3">
                {impactCurrent ? (
                  <div className="space-y-1.5" data-testid="impact-preview">
                    <p className="text-sm">
                      {t("admin.compliance.add.impact", {
                        users: impact.affected_users,
                        marketplaces: impact.affected_marketplaces,
                      })}
                    </p>
                    {marketplacesBlock ? (
                      <p className="text-xs text-[var(--status-error)]">
                        {t("admin.compliance.add.marketplacesBlock")}{" "}
                        <Link to="/admin/overview" className="underline">
                          {t("admin.compliance.add.marketplacesLink")}
                        </Link>
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {t("admin.compliance.add.previewHint")}
                  </p>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!formValid || busy}
                  onClick={() => void runPreview(forceNote != null)}
                >
                  {t("admin.compliance.add.preview")}
                </Button>
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={!canSave || busy}
              onClick={() => (isEdit ? void runUpdate() : void runSave(forceNote != null))}
              data-testid="blocked-country-submit"
            >
              {isEdit ? t("common.save") : t("admin.compliance.add.submit")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ProtectedCountryWarning
        open={pendingStep != null}
        countryCode={countryCode ?? ""}
        countryName={countryName}
        pending={busy}
        onCancel={() => setPendingStep(null)}
        onConfirm={onProtectedConfirm}
      />
    </>
  );
}
