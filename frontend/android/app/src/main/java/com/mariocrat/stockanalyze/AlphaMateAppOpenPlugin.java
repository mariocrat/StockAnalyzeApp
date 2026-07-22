package com.mariocrat.stockanalyze;

import android.app.Activity;
import androidx.annotation.NonNull;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.appopen.AppOpenAd;

@CapacitorPlugin(name = "AlphaMateAppOpen")
public class AlphaMateAppOpenPlugin extends Plugin {
    private static final long MAX_CACHE_AGE_MS = 4L * 60L * 60L * 1000L;

    private AppOpenAd appOpenAd;
    private String adUnitId = "";
    private long loadedAtMs = 0L;
    private boolean loading = false;
    private boolean showing = false;

    @PluginMethod
    public void prepare(PluginCall call) {
        String requestedAdId = call.getString("adId", "").trim();
        if (requestedAdId.isEmpty()) {
            call.reject("App Open ad unit ID is required.");
            return;
        }
        adUnitId = requestedAdId;

        getActivity().runOnUiThread(() -> loadAd(call));
    }

    @PluginMethod
    public void show(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            if (showing) {
                call.resolve(result("shown", false, "already_showing"));
                return;
            }
            if (!hasFreshAd()) {
                clearAd();
                call.resolve(result("shown", false, "not_ready"));
                loadAd(null);
                return;
            }

            Activity activity = getActivity();
            AppOpenAd ad = appOpenAd;
            showing = true;
            ad.setFullScreenContentCallback(new FullScreenContentCallback() {
                @Override
                public void onAdDismissedFullScreenContent() {
                    showing = false;
                    clearAd();
                    call.resolve(result("shown", true, "dismissed"));
                    loadAd(null);
                }

                @Override
                public void onAdFailedToShowFullScreenContent(@NonNull AdError adError) {
                    showing = false;
                    clearAd();
                    call.reject("App Open ad failed to show: " + adError.getCode());
                    loadAd(null);
                }

                @Override
                public void onAdShowedFullScreenContent() {
                    appOpenAd = null;
                }
            });
            ad.show(activity);
        });
    }

    private void loadAd(PluginCall call) {
        if (hasFreshAd()) {
            if (call != null) call.resolve(result("prepared", true, "cached"));
            return;
        }
        if (loading) {
            if (call != null) call.resolve(result("prepared", false, "loading"));
            return;
        }
        if (adUnitId.isEmpty()) {
            if (call != null) call.reject("App Open ad unit ID is required.");
            return;
        }

        loading = true;
        AppOpenAd.load(
            getContext(),
            adUnitId,
            new AdRequest.Builder().build(),
            new AppOpenAd.AppOpenAdLoadCallback() {
                @Override
                public void onAdLoaded(@NonNull AppOpenAd ad) {
                    loading = false;
                    appOpenAd = ad;
                    loadedAtMs = System.currentTimeMillis();
                    if (call != null) call.resolve(result("prepared", true, "loaded"));
                }

                @Override
                public void onAdFailedToLoad(@NonNull LoadAdError loadAdError) {
                    loading = false;
                    clearAd();
                    if (call != null) call.reject("App Open ad failed to load: " + loadAdError.getCode());
                }
            }
        );
    }

    private boolean hasFreshAd() {
        return appOpenAd != null && System.currentTimeMillis() - loadedAtMs < MAX_CACHE_AGE_MS;
    }

    private void clearAd() {
        appOpenAd = null;
        loadedAtMs = 0L;
    }

    private JSObject result(String key, boolean success, String reason) {
        JSObject result = new JSObject();
        result.put(key, success);
        result.put("reason", reason);
        return result;
    }
}
