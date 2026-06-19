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
            // Scroll to the session detail callout after Shiny re-renders it
            setTimeout(function () {
                var detail = document.getElementById('results-lon_session_detail');
                if (detail && detail.firstElementChild) {
                    detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }, 350);
        });
    }
    // Re-attach whenever the chart might be re-rendered
    var _obs = new MutationObserver(_attachLon);
    _obs.observe(document.body, {childList: true, subtree: true});
    _attachLon();
})();
