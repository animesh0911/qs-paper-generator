import pgvector.django
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0003_retrieval_chunk"),
    ]

    operations = [
        pgvector.django.VectorExtension(),
        migrations.AddField(
            model_name="retrievalchunk",
            name="embedding",
            field=pgvector.django.VectorField(null=True),
        ),
        migrations.AddField(
            model_name="retrievalchunk",
            name="embedding_model",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="retrievalchunk",
            name="embedding_version",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddConstraint(
            model_name="retrievalchunk",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        embedding__isnull=True,
                        embedding_model="",
                        embedding_version="",
                    )
                    | (
                        models.Q(embedding__isnull=False)
                        & ~models.Q(embedding_model="")
                        & ~models.Q(embedding_version="")
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
                  AND embedding_version = 'v1';
            """,
            reverse_sql=("DROP INDEX IF EXISTS retrieval_chunk_fixed_test_v1_hnsw;"),
        ),
    ]
