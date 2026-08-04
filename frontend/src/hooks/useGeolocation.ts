import { useCallback, useState } from "react";

interface GeolocationState {
  loading: boolean;
  error: string | null;
}

export function useGeolocation(onLocated: (lat: number, lon: number) => void) {
  const [state, setState] = useState<GeolocationState>({ loading: false, error: null });

  const locate = useCallback(() => {
    if (!navigator.geolocation) {
      setState({ loading: false, error: "Geolocation is not supported by this browser." });
      return;
    }
    setState({ loading: true, error: null });
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setState({ loading: false, error: null });
        onLocated(position.coords.latitude, position.coords.longitude);
      },
      (error) => {
        setState({ loading: false, error: error.message });
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }, [onLocated]);

  return { ...state, locate };
}
