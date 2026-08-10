(function () {
    "use strict";

    var overlay = null;
    var styleAdded = false;

    function ensureStyle() {
        if (styleAdded) return;
        styleAdded = true;
        var style = document.createElement("style");
        style.textContent =
            "#submit-overlay{position:fixed;inset:0;background:rgba(4,10,20,.7);" +
            "backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);z-index:20000;" +
            "display:none;align-items:center;justify-content:center;flex-direction:column;gap:18px;}" +
            "#submit-overlay.active{display:flex;}" +
            "#submit-spinner{width:56px;height:56px;border-radius:50%;" +
            "border:3px solid rgba(255,255,255,.15);border-top-color:#00f0ff;" +
            "animation:submit-spin .9s linear infinite;}" +
            "@keyframes submit-spin{to{transform:rotate(360deg);}}" +
            "#submit-text{color:#e3f2fd;font-size:15px;letter-spacing:1px;}";
        document.head.appendChild(style);
    }

    function showOverlay() {
        ensureStyle();
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.id = "submit-overlay";
            overlay.innerHTML =
                '<div id="submit-spinner"></div><div id="submit-text">Sila tunggu...</div>';
            document.body.appendChild(overlay);
        }
        overlay.classList.add("active");
    }

    function hideOverlay() {
        if (overlay) overlay.classList.remove("active");
    }

    function pending(form) {
        return form.getAttribute("data-submitting") === "1";
    }

    function markPending(form) {
        form.setAttribute("data-submitting", "1");
    }

    function disableButtons(form) {
        form.querySelectorAll("[type='submit']").forEach(function (btn) {
            btn.disabled = true;
        });
    }

    document.addEventListener("submit", function (e) {
        var form = e.target.closest("form");
        if (!form) return;

        if (pending(form)) {
            e.preventDefault();
            return;
        }

        markPending(form);

        // Modal forms (async fetch handled by page script) only get the overlay.
        if (form.closest("#detail-body")) {
            showOverlay();
            return;
        }

        // Native submits: overlay + disable buttons; page navigates on POST.
        disableButtons(form);
        showOverlay();
    });

    window.submitGuard = {
        done: function (form) {
            if (form) {
                form.removeAttribute("data-submitting");
                form.querySelectorAll("[type='submit']").forEach(function (btn) {
                    btn.disabled = false;
                });
            }
            hideOverlay();
        }
    };
})();
