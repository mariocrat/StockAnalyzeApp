package com.mariocrat.stockanalyze;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(AlphaMateAppOpenPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
