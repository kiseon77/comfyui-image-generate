<script lang="ts">
	import { onMount } from 'svelte';
	import { writable } from 'svelte/store';
	import { page } from '$app/stores';
	import { get } from 'svelte/store';

	let workflow = '';
	let imageUrl = '';
	let prompt: string = '';
	let subfolder = '';
	let errorMessage = '';
	let fileErrorMessage = '';
	let uploadStatus = '';
	let arr = writable<any[]>([]);
	let isGenerating = false;
	let generatedImages: string[] = [];
	let showMultipleImages = false;

	const eyeLeft = writable({ x: 0, y: 0 });
	const eyeRight = writable({ x: 0, y: 0 });

	let container: HTMLElement;
	let eyeRadius = 6;
	let eyeCenterLeft: { x: number; y: number };
	let eyeCenterRight: { x: number; y: number };

	function setIsGenerating(value: boolean) {
		isGenerating = value;
		localStorage.setItem('isGenerating', value ? 'true' : 'false');
	}

	onMount(() => {
		const saved = localStorage.getItem('isGenerating');
		isGenerating = saved === 'true'; // 저장된 값이 있으면 복원

		// 필요하다면 다른 초기화 코드도 추가
	});

	function updateEyePosition(event: MouseEvent) {
		const { clientX, clientY } = event;

		const moveEye = (center: { x: number; y: number }) => {
			const dx = clientX - center.x;
			const dy = clientY - center.y;
			const angle = Math.atan2(dy, dx);

			return {
				x: Math.cos(angle) * eyeRadius,
				y: Math.sin(angle) * eyeRadius
			};
		};

		eyeLeft.set(moveEye(eyeCenterLeft));
		eyeRight.set(moveEye(eyeCenterRight));
	}

	function resetEyes() {
		eyeLeft.set({ x: 0, y: 0 });
		eyeRight.set({ x: 0, y: 0 });
	}

	onMount(() => {
		const rect = container.getBoundingClientRect();
		eyeCenterLeft = {
			x: rect.left + rect.width * 0.35,
			y: rect.top + rect.height * 0.4
		};
		eyeCenterRight = {
			x: rect.left + rect.width * 0.65,
			y: rect.top + rect.height * 0.4
		};

		container.addEventListener('mousemove', updateEyePosition);
		container.addEventListener('mouseleave', resetEyes);

		return () => {
			container.removeEventListener('mousemove', updateEyePosition);
			container.removeEventListener('mouseleave', resetEyes);
		};
	});

	onMount(() => {
		const url = get(page).url;
		workflow = url.searchParams.get('workflow') ?? '';
	});

	async function generate(event: Event) {
		event.preventDefault();
		errorMessage = '';
		setIsGenerating(true);
		generatedImages = [];
		showMultipleImages = false;

		try {
			let response;

			try {
				const jsonData = JSON.parse(prompt);

				if (jsonData && jsonData.events && Array.isArray(jsonData.events)) {
					showMultipleImages = true;

					response = await fetch('http://127.0.0.1:5000/generate', {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({ prompt: jsonData, workflow, subfolder })
					});
				} else {
					throw new Error('올바른 JSON 형식이 아닙니다.');
				}
			} catch {
				// 일반 텍스트로 처리
				response = await fetch('http://127.0.0.1:5000/generate', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ workflow, prompt, subfolder })
				});
			}

			const data = await response.json();

			if (data.image_urls && data.image_urls.length > 0) {
				const validUrls = data.image_urls.filter((url: string) => url !== 'timeout');

				if (validUrls.length > 0) {
					generatedImages = validUrls;
					imageUrl = validUrls[0];
				} else {
					throw new Error('이미지 생성에 실패했습니다. 다시 시도해주세요.');
				}
			} else {
				throw new Error('이미지 생성에 실패했습니다. 다시 시도해주세요.');
			}
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '서버와의 연결에 실패했습니다.';
			console.error(error);
		} finally {
			setIsGenerating(false); // 무조건 false로 재설정
		}
	}

	function selectImage(url: string) {
		imageUrl = url;
	}

	async function onFileSelected(event: Event) {
		fileErrorMessage = '';
		uploadStatus = '';
		const input = event.target as HTMLInputElement;
		if (!input.files || input.files.length === 0) {
			fileErrorMessage = '파일을 선택해주세요.';
			return;
		}
		const file = input.files[0];
		const reader = new FileReader();

		reader.onload = async () => {
			try {
				const json = JSON.parse(reader.result as string);
				arr.set(json);

				// JSON 내용을 textarea에 표시
				prompt = JSON.stringify(json, null, 2); // 들여쓰기 포함한 문자열
			} catch (e) {
				fileErrorMessage = 'JSON 파싱에 실패했습니다.';
				console.error(e);
			}
		};

		reader.onerror = () => {
			fileErrorMessage = '파일 읽기에 실패했습니다.';
		};

		reader.readAsText(file);
	}
</script>

<section class="container relative p-4">
	<form
		bind:this={container}
		on:submit={generate}
		class="absolute left-1/2 top-1/2 w-3/5 -translate-x-1/2 -translate-y-1/2 transform rounded-2xl bg-teal-500 p-6 shadow-lg outline outline-black/5"
	>
		<div class="rounded-xl bg-teal-600 text-neutral-950">
			<div class="min-h-[300px] w-full rounded-lg bg-teal-200">
				{#if isGenerating}
					<div class="flex h-[300px] items-center justify-center">
						<p class="text-lg font-semibold">이미지 생성 중...</p>
					</div>
				{:else if imageUrl}
					<div class="mx-auto mt-4 max-h-[500px] w-full overflow-auto text-center">
						<img src={imageUrl} alt="생성된 캐릭터 이미지" class="mx-auto w-auto object-contain" />
					</div>

					{#if showMultipleImages && generatedImages.length > 1}
						<div class="mt-4 flex flex-wrap justify-center gap-2 p-2">
							{#each generatedImages as url, i}
								<button
									type="button"
									class="cursor-pointer border-none bg-transparent p-0"
									on:click={() => selectImage(url)}
									on:keydown={(e) => {
										if (e.key === 'Enter' || e.key === ' ') {
											e.preventDefault();
											selectImage(url);
										}
									}}
									aria-label={`생성된 이미지 ${i + 1} 선택`}
								>
									<img
										src={url}
										alt={`생성된 이미지 ${i + 1}`}
										class="h-16 w-auto border-2 border-transparent object-cover hover:border-teal-600"
										class:border-teal-800={url === imageUrl}
									/>
								</button>
							{/each}
						</div>
					{/if}
				{:else}
					<div class="relative m-auto h-[300px] w-[300px]">
						<div
							class="absolute left-[30%] top-[40%] flex h-6 w-6 items-center justify-center overflow-hidden rounded-full bg-white"
						>
							<div
								class="h-2 w-2 rounded-full bg-black transition-transform duration-100"
								style="transform: translate({$eyeLeft.x}px, {$eyeLeft.y}px)"
							></div>
						</div>
						<div
							class="absolute left-[60%] top-[40%] flex h-6 w-6 items-center justify-center overflow-hidden rounded-full bg-white"
						>
							<div
								class="h-2 w-2 rounded-full bg-black transition-transform duration-100"
								style="transform: translate({$eyeRight.x}px, {$eyeRight.y}px)"
							></div>
						</div>
						<div class="absolute left-[45%] top-[60%] h-1 w-4 rounded-full bg-black"></div>
					</div>
				{/if}
			</div>
		</div>
		<input
			bind:value={subfolder}
			type="text"
			placeholder="폴더이름"
			class="my-4 rounded-md border border-teal-100 bg-teal-100 p-2"
		/>
		<input type="file" accept=".json" on:change={onFileSelected} />
		{#if fileErrorMessage}
			<p class="text-red-500">{fileErrorMessage}</p>
		{/if}
		<textarea
			bind:value={prompt}
			placeholder="캐릭터 스타일 입력"
			class="max-h-2/5 my-4 w-full rounded-md border border-teal-100 bg-teal-100 p-2"
		>
		</textarea>
		<div class="flex justify-between">
			<div></div>
			<button
				type="submit"
				class="
				active:inset-shadow-[0_8px_0_0_theme('colors.amber.800')]
				w-15 aspect-square -translate-y-2 rounded-full bg-red-600
				text-white
				shadow-[0_4px_0_0_theme('colors.red.800')] transition-all duration-150
				ease-in-out
				hover:translate-y-0 hover:shadow-none
				active:translate-y-0
				active:bg-red-700 active:text-white/70
				active:shadow-none
				disabled:translate-y-0 disabled:cursor-not-allowed disabled:bg-red-400 disabled:opacity-50 disabled:shadow-none
			"
				disabled={isGenerating}
			>
				{isGenerating ? '생성 중...' : '생성'}
			</button>
		</div>
	</form>

	{#if errorMessage}
		<p class="text-red-500">{errorMessage}</p>
	{/if}
</section>
