from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0004_retrieval_chunk_embeddings"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS retrieval_chunk_fixed_test_v1_hnsw;",
            reverse_sql="""
                CREATE INDEX retrieval_chunk_fixed_test_v1_hnsw
                ON corpus_retrievalchunk
                USING hnsw ((embedding::vector(3)) vector_cosine_ops)
                WHERE embedding_model = 'fixed-vector-test'
                  AND embedding_version = 'v1';
            """,
        ),
        migrations.RemoveConstraint(
            model_name="retrievalchunk",
            name="retrieval_chunk_embedding_profile_complete",
        ),
        migrations.AddField(
            model_name="retrievalchunk",
            name="embedding_dimensions",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunSQL(
            sql="""
                UPDATE corpus_retrievalchunk
                SET embedding_dimensions = vector_dims(embedding)
                WHERE embedding IS NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddConstraint(
            model_name="retrievalchunk",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        embedding__isnull=True,
                        embedding_model="",
                        embedding_version="",
                        embedding_dimensions__isnull=True,
                    )
                    | (
                        models.Q(embedding__isnull=False)
                        & ~models.Q(embedding_model="")
                        & ~models.Q(embedding_version="")
                        & models.Q(embedding_dimensions__isnull=False)
                    )
                ),
                name="retrieval_chunk_embedding_profile_complete",
            ),
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX retrieval_chunk_fixed_test_v1_hnsw
                ON corpus_retrievalchunk
                USING hnsw ((embedding::vector(3)) vector_cosine_ops)
                WHERE embedding_model = 'fixed-vector-test'
                  AND embedding_version = 'v1'
                  AND embedding_dimensions = 3;
            """,
            reverse_sql=("DROP INDEX IF EXISTS retrieval_chunk_fixed_test_v1_hnsw;"),
        ),
    ]
