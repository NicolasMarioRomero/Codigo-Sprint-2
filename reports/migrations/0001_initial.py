from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True)),
                ('company_id',   models.IntegerField(db_index=True)),
                ('project_id',   models.IntegerField(db_index=True)),
                ('service_name', models.CharField(max_length=64)),
                ('provider',     models.CharField(
                    choices=[('aws', 'AWS'), ('gcp', 'GCP'), ('azure', 'Azure')],
                    default='aws', max_length=16,
                )),
                ('cost',         models.FloatField()),
                ('usage',        models.FloatField()),
                ('currency',     models.CharField(default='USD', max_length=8)),
                ('timestamp',    models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={'db_table': 'reports', 'ordering': ['-timestamp']},
        ),
    ]
