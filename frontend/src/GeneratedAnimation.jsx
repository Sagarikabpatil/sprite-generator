function GeneratedAnimation({ result }) {
  return (
    <section className="mt-12 border-t border-slate-700 pt-10" aria-live="polite">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">
            Animation result
          </p>
          <h2 className="mt-2 text-3xl font-bold text-white">{result.action} cycle</h2>
        </div>
        <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-100">
          {result.frame_count} frames
        </span>
      </div>

      <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-8">
          <section className="rounded-2xl border border-slate-700 bg-slate-950/70 p-5 shadow-xl">
            <h3 className="mb-4 text-xl font-semibold text-white">Generated video</h3>
            <video
              className="aspect-video w-full rounded-xl border border-slate-700 bg-black object-contain"
              controls
              preload="metadata"
              src={result.generated_video}
            >
              Your browser does not support video playback.
            </video>
          </section>

          <section>
            <h3 className="mb-4 text-xl font-semibold text-white">Animation frames</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {result.frames.map((frameUrl, index) => (
                <figure
                  className="overflow-hidden rounded-xl border border-slate-700 bg-slate-950/70 p-2"
                  key={frameUrl}
                >
                  <div className="flex aspect-square items-center justify-center rounded-lg bg-slate-800 p-2">
                    <img
                      src={frameUrl}
                      alt={`Animation frame ${index + 1}`}
                      className="max-h-full w-full object-contain"
                    />
                  </div>
                  <figcaption className="pt-2 text-center text-sm text-slate-300">
                    Frame {index + 1}
                  </figcaption>
                </figure>
              ))}
            </div>
          </section>
        </div>

        <div className="space-y-8">
          <section className="rounded-2xl border border-cyan-400/30 bg-slate-950/70 p-5 shadow-xl">
            <h3 className="mb-4 text-xl font-semibold text-white">Sprite sheet</h3>
            <div className="rounded-xl bg-slate-800 p-3">
              <img
                src={result.sprite_sheet}
                alt={`${result.action} sprite sheet`}
                className="w-full rounded-lg object-contain"
              />
            </div>
          </section>

          <section className="rounded-2xl border border-slate-700 bg-slate-950/70 p-5">
            <h3 className="mb-4 text-xl font-semibold text-white">Generation info</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between gap-4 border-b border-slate-800 pb-3">
                <dt className="text-slate-400">Action</dt>
                <dd className="font-medium capitalize text-white">{result.action}</dd>
              </div>
              <div className="flex justify-between gap-4 border-b border-slate-800 pb-3">
                <dt className="text-slate-400">Frame count</dt>
                <dd className="font-medium text-white">{result.frame_count}</dd>
              </div>
              <div className="border-b border-slate-800 pb-3">
                <dt className="text-slate-400">Provider</dt>
                <dd className="mt-1 break-words font-medium text-white">{result.provider}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Generation report</dt>
                <dd className="mt-1 break-words leading-6 text-slate-200">
                  {result.generation_report || "No report returned."}
                </dd>
              </div>
            </dl>
          </section>
        </div>
      </div>
    </section>
  );
}

export default GeneratedAnimation;
