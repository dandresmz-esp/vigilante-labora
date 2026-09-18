// Optional local fallback; GitHub uses native Tesseract. No cloud OCR or model API.
const {createWorker} = require(process.env.TESSERACT_JS_MODULE || 'tesseract.js');
(async () => {
  const worker = await createWorker('spa+cat', 1, {cachePath: process.env.OCR_CACHE || 'runtime'});
  try {
    let best = null;
    for (const mode of ['3', '6', '11']) {
      await worker.setParameters({tessedit_pageseg_mode: mode});
      const {data} = await worker.recognize(process.argv[2]);
      if (!best || data.confidence > best.confidence) best = data;
      if (data.confidence >= 45 && data.text.trim().length >= 25) {
        process.stdout.write(data.text);
        return;
      }
    }
    throw new Error('OCR confidence too low');
  } finally { await worker.terminate(); }
})().catch(() => { process.stderr.write('OCR failed; manual review required.'); process.exitCode=1; });
