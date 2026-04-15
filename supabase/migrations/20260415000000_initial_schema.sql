-- ── Profiles (auto-populated from auth.users on signup) ─────────────────────
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text unique,
  full_name   text,
  avatar_url  text,
  created_at  timestamptz default now() not null
);

-- ── Jobs (replaces in-memory JobStore) ───────────────────────────────────────
create table if not exists public.jobs (
  job_id                    uuid primary key default gen_random_uuid(),
  user_id                   uuid references public.profiles(id) on delete set null,
  status                    text not null default 'IN_QUEUE',
  fal_request_id            text,
  fal_endpoint              text,
  fal_status_url            text,
  fal_response_url          text,
  mode                      text not null default 'text-to-video',
  resolution                text not null default '480p',
  duration                  text not null default '5',
  aspect_ratio              text not null default '16:9',
  generate_audio            boolean default true,
  user_prompt               text not null,
  submitted_prompt          text,
  submitted_prompt_language text,
  generated_prompt_en       text,
  generated_prompt_zh       text,
  image_url                 text,
  video_url                 text,
  local_path                text,
  seed                      bigint,
  error                     text,
  created_at                timestamptz default now() not null,
  completed_at              timestamptz
);

-- ── Row Level Security ────────────────────────────────────────────────────────
alter table public.profiles enable row level security;
alter table public.jobs     enable row level security;

-- profiles: users can only read/update their own row
create policy "own profile select" on public.profiles
  for select using (auth.uid() = id);

create policy "own profile update" on public.profiles
  for update using (auth.uid() = id);

-- jobs: users can only read their own jobs
create policy "own jobs select" on public.jobs
  for select using (auth.uid() = user_id);

-- jobs: service role / postgres superuser can insert & update (backend uses DATABASE_URL)
create policy "service insert jobs" on public.jobs
  for insert with check (true);

create policy "service update jobs" on public.jobs
  for update using (true);

-- ── Auto-create profile row when a new user signs up ─────────────────────────
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, email, full_name)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1))
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
