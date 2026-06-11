(function () {
    function _attachLon() {
        var wrap = document.getElementById('mt-lon-chart-wrapper');
        if (!wrap) { setTimeout(_attachLon, 600); return; }
        var div = wrap.querySelector('.plotly-graph-div');
        if (!div || !div.on) { setTimeout(_attachLon, 600); return; }
        if (div._mt_lon_bound) return;
        div._mt_lon_bound = true;
        div.on('plotly_click', function (data) {
            if (!data.points || !data.points.length) return;
            var pt = data.points[0];
            var cd = pt.customdata;
            if (!cd || cd.length < 4) return;
            if (!window.Shiny) return;
            Shiny.setInputValue('results-lon_click', {
                date:    String(cd[0]),
                pl_nl:   String(cd[1]),
                delta:   cd[2],
                session: cd[3],
                stress:  pt.y,
            }, {priority: 'event'});
        });
    }
    // Re-attach whenever the chart might be re-rendered
    var _obs = new MutationObserver(_attachLon);
    _obs.observe(document.body, {childList: true, subtree: true});
    _attachLon();
})();
