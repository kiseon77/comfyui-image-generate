<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	let workflowList: string[] = [];

	onMount(() => {
		async function getWorkflowList() {
			const res = await fetch('http://127.0.0.1:5000/workflows');
			const data = await res.json();
			workflowList = [...data.workflows];
		}
		getWorkflowList();
	});

	function handleNextPage(workflow: string) {
		goto(`/prompt?workflow=${encodeURIComponent(workflow)}`);
	}
</script>

<main class="container relative p-4">
	<div
		class="absolute left-1/2 top-1/2 w-3/5 -translate-x-1/2 -translate-y-1/2 transform rounded-2xl bg-teal-500 p-6 shadow-lg outline outline-black/5"
	>
		<div class="mb-3 flex justify-between">
			<i class="material-symbols-rounded" style="font-size: 32px; color:black; opacity:0.2">
				add_circle
			</i>
			<div>
				<i
					class="material-symbols-rounded"
					style="font-size: 32px; color:black; opacity:0.2; transform: scaleX(-1);"
				>
					menu_open
				</i>
				<span class="material-symbols-rounded" style="font-size: 32px; color:black; opacity:0.2">
					menu
				</span>
				<i class="material-symbols-rounded" style="font-size: 32px; color:black; opacity:0.2">
					menu_open
				</i>
			</div>
			<i class="material-symbols-rounded" style="font-size: 32px; color:black;  opacity:0.2">
				add_circle
			</i>
		</div>
		<div class="rounded-xl bg-teal-600 p-3 text-neutral-950">
			<div class=" h-full w-full rounded-lg bg-teal-200 p-3">
				<h3 class=" text-2xl font-semibold opacity-80">Kiseon's Comfyui</h3>
				<p class="mt-3 font-semibold leading-6 opacity-60">우당탕탕 comfyui 공장입니다.</p>
			</div>
		</div>
		<div class="mt-6">
			{#if workflowList.length > 0}
				{#each workflowList as workflow}
					<div class="inline-block rounded-lg bg-teal-600 p-3">
						<button
							value={workflow}
							on:click={() => handleNextPage(workflow)}
							class="active:inset-shadow-[0_8px_0_0_theme('colors.amber.800')] -translate-y-2 rounded-lg bg-amber-600 px-6 py-3
							text-white
							shadow-[0_8px_0_0_theme('colors.amber.800')] transition-all duration-150
							ease-in-out
							hover:translate-y-0 hover:shadow-none active:translate-y-0
						  active:bg-amber-700 active:text-white/70
							active:shadow-none"
						>
							{workflow}
						</button>
					</div>
				{/each}
			{:else}
				<p>워크플로를 불러오는 중...</p>
			{/if}
		</div>
		<div class="mt-8 flex justify-between">
			<i class="material-symbols-rounded" style="font-size: 32px; color:black; opacity:0.2">
				add_circle
			</i>
			<i class="material-symbols-rounded" style="font-size: 32px; color:black; opacity:0.2">
				menu
			</i>
			<i class="material-symbols-rounded" style="font-size: 32px; color:black;  opacity:0.2">
				add_circle
			</i>
		</div>
	</div>
</main>
