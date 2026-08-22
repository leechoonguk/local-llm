Write a JavaScript (CommonJS, Node) module exporting `debounce(fn, wait, {leading=false, trailing=true}={})`.
Returned function: when `leading`, call fn immediately on the first call of a burst; when `trailing`, call fn with the LAST call's arguments after `wait` ms of silence.
If both are set and only one call happens in the burst, fn is invoked only once. The returned function has a `.cancel()` method that drops any pending trailing call.
Use setTimeout/clearTimeout. Output ONLY the code in a single ```javascript block, no explanation.
