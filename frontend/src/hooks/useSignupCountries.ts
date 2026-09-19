/**
 * Countries offered on the registration form. Source of truth is the public
 * WP6 endpoint (active dim_country minus the blocked list); until it ships
 * the request 404s and the bundled ISO reference list stands in — real
 * reference data, not a mock (gap logged in FRONTEND_BACKEND_REQUESTS.md).
 */

import { useQuery } from "@tanstack/react-query";
import { authApi } from "@/api/auth";
import { COUNTRIES } from "@/lib/countries";

export interface SignupCountry {
  code: string;
  name: string;
}

const LOCAL_REFERENCE: SignupCountry[] = COUNTRIES.map((country) => ({
  code: country.code,
  name: country.name,
})).sort((a, b) => a.name.localeCompare(b.name));

export function useSignupCountries(): { countries: SignupCountry[]; isLoading: boolean } {
  const query = useQuery({
    queryKey: ["auth", "countries"],
    queryFn: () => authApi.getCountries().then((r) => r.data.items),
    staleTime: 60 * 60 * 1000,
    retry: false,
  });

  if (query.data) {
    return {
      countries: query.data.map((row) => ({ code: row.code, name: row.name })),
      isLoading: false,
    };
  }
  return { countries: query.isError ? LOCAL_REFERENCE : [], isLoading: query.isLoading };
}
