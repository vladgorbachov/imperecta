import type { AccountType, LegalDocument } from "@/lib/legalVersions";

export interface ConsentFormState {
  accountType: AccountType | null;
  businessUseConfirmed: boolean;
  adultConfirmed: boolean;
  documentsAccepted: boolean;
}

export const EMPTY_CONSENT_STATE: ConsentFormState = {
  accountType: null,
  businessUseConfirmed: false,
  adultConfirmed: false,
  documentsAccepted: false,
};

/** Static i18n key maps — the coverage guard forbids template-literal keys. */
export const DOCUMENT_LABELS: Record<LegalDocument, string> = {
  terms: "legal.terms",
  privacy: "legal.privacy",
  aup: "legal.aup",
};

export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  business: "auth.accountType.business",
  sole_trader: "auth.accountType.soleTrader",
};
