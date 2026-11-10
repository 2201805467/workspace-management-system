CREATE EXTENSION IF NOT EXISTS pg_trgm;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname='workspace_arabic') THEN
  CREATE TEXT SEARCH CONFIGURATION public.workspace_arabic (COPY = pg_catalog.simple);
 END IF;
END $$;

CREATE OR REPLACE FUNCTION public.workspace_normalize(value text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
 SELECT regexp_replace(lower(translate(regexp_replace(replace(coalesce(value,''),'مسئول','مسؤول'),
 '[ًٌٍَُِّْٰـ]','','g'),'أإآٱىؤئ','اااايوي')), '\mال([ء-ي]{3,})', '\1', 'g');
$$;

CREATE OR REPLACE FUNCTION public.workspace_vector(title text, summary text, body text) RETURNS tsvector
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
 SELECT setweight(to_tsvector('public.workspace_arabic'::regconfig, public.workspace_normalize(title)), 'A') ||
        setweight(to_tsvector('pg_catalog.english'::regconfig, public.workspace_normalize(title)), 'A') ||
        setweight(to_tsvector('public.workspace_arabic'::regconfig, public.workspace_normalize(summary)), 'B') ||
        setweight(to_tsvector('pg_catalog.english'::regconfig, public.workspace_normalize(summary)), 'B') ||
        setweight(to_tsvector('public.workspace_arabic'::regconfig, public.workspace_normalize(body)), 'C') ||
        setweight(to_tsvector('pg_catalog.english'::regconfig, public.workspace_normalize(body)), 'C');
$$;

CREATE OR REPLACE FUNCTION public.workspace_article_index() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 NEW.search_title := public.workspace_normalize(NEW.title);
 NEW.search_vector := public.workspace_vector(NEW.title,NEW.summary,NEW.content);
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS knowledge_article_index ON knowledge_articles;
CREATE TRIGGER knowledge_article_index BEFORE INSERT OR UPDATE OF title,summary,content,status,language
ON knowledge_articles FOR EACH ROW EXECUTE FUNCTION public.workspace_article_index();

CREATE OR REPLACE FUNCTION public.workspace_file_index() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE file_name text; is_deleted boolean;
BEGIN
 SELECT original_name, deleted_at IS NOT NULL INTO file_name,is_deleted FROM files WHERE id=NEW.file_id;
 NEW.search_title := public.workspace_normalize(file_name);
 NEW.search_vector := CASE WHEN is_deleted THEN NULL ELSE public.workspace_vector(file_name,'',
   CASE WHEN NEW.indexing_status='ready' THEN NEW.extracted_text ELSE '' END) END;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS workspace_file_search ON file_search_index;
CREATE TRIGGER workspace_file_search BEFORE INSERT OR UPDATE ON file_search_index
FOR EACH ROW EXECUTE FUNCTION public.workspace_file_index();

CREATE OR REPLACE FUNCTION public.workspace_queue_file() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO file_search_index(id,file_id,extracted_text,indexing_status,updated_at,search_title)
 VALUES(NEW.id,NEW.id,'',CASE WHEN NEW.deleted_at IS NULL THEN 'pending' ELSE 'failed' END,now(),'')
 ON CONFLICT(file_id) DO UPDATE SET updated_at=now(),
  extracted_text=CASE WHEN NEW.deleted_at IS NOT NULL THEN '' ELSE file_search_index.extracted_text END,
  indexing_status=CASE WHEN NEW.deleted_at IS NOT NULL THEN 'failed' ELSE 'pending' END,
  error_code=CASE WHEN NEW.deleted_at IS NOT NULL THEN 'deleted' ELSE NULL END,
  lease_token=NULL;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS workspace_queue_file ON files;
CREATE TRIGGER workspace_queue_file AFTER INSERT OR UPDATE OF original_name,deleted_at ON files
FOR EACH ROW EXECUTE FUNCTION public.workspace_queue_file();

INSERT INTO file_search_index(id,file_id,extracted_text,indexing_status,updated_at,search_title)
SELECT id,id,'','pending',now(),'' FROM files WHERE deleted_at IS NULL ON CONFLICT(file_id) DO NOTHING;
