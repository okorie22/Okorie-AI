"""
☁️ ITORO Cloud Storage Manager
Handles data persistence across multiple cloud providers

Supported providers: Supabase, Firebase, MongoDB Atlas, AWS S3
Provides unified interface for commerce agents to store/retrieve data.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from abc import ABC, abstractmethod
import logging

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# 🌐 CLOUD STORAGE INTERFACE
# =============================================================================

class CloudStorageInterface(ABC):
    """Abstract base class for cloud storage implementations"""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to cloud storage"""
        pass

    @abstractmethod
    def store_data(self, collection: str, data: Union[Dict, List], key: Optional[str] = None) -> bool:
        """Store data in specified collection/table"""
        pass

    @abstractmethod
    def retrieve_data(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve data from specified collection/table"""
        pass

    @abstractmethod
    def update_data(self, collection: str, key: str, updates: Dict) -> bool:
        """Update existing data"""
        pass

    @abstractmethod
    def delete_data(self, collection: str, key: str) -> bool:
        """Delete data by key"""
        pass

    @abstractmethod
    def list_collections(self) -> List[str]:
        """List available collections/tables"""
        pass

# =============================================================================
# 🗄️ SUPABASE IMPLEMENTATION
# =============================================================================

class SupabaseStorage(CloudStorageInterface):
    """Supabase cloud storage implementation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to Supabase"""
        try:
            from supabase import create_client, Client
            self.client: Client = create_client(
                self.config['url'],
                self.config['anon_key']
            )
            self.connected = True
            logger.info("✅ Connected to Supabase")
            return True
        except ImportError:
            logger.error("❌ Supabase library not installed. Install with: pip install supabase")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to connect to Supabase: {e}")
            return False

    def store_data(self, collection: str, data: Union[Dict, List], key: Optional[str] = None) -> bool:
        """Store data in Supabase table"""
        if not self.connected:
            return False

        try:
            if isinstance(data, list):
                # Bulk insert
                result = self.client.table(collection).insert(data).execute()
            else:
                # Single insert/update
                if key:
                    # Update existing record
                    result = self.client.table(collection).update(data).eq('id', key).execute()
                else:
                    # Insert new record
                    result = self.client.table(collection).insert(data).execute()

            logger.info(f"✅ Stored {len(data) if isinstance(data, list) else 1} records in {collection}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to store data in {collection}: {e}")
            return False

    def retrieve_data(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve data from Supabase table"""
        if not self.connected:
            return []

        try:
            supabase_query = self.client.table(collection).select('*')

            if query:
                for key, value in query.items():
                    supabase_query = supabase_query.eq(key, value)

            if limit:
                supabase_query = supabase_query.limit(limit)

            result = supabase_query.execute()
            data = result.data if hasattr(result, 'data') else []
            logger.info(f"✅ Retrieved {len(data)} records from {collection}")
            return data
        except Exception as e:
            logger.error(f"❌ Failed to retrieve data from {collection}: {e}")
            return []

    def update_data(self, collection: str, key: str, updates: Dict) -> bool:
        """Update data in Supabase table"""
        if not self.connected:
            return False

        try:
            result = self.client.table(collection).update(updates).eq('id', key).execute()
            logger.info(f"✅ Updated record {key} in {collection}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update data in {collection}: {e}")
            return False

    def delete_data(self, collection: str, key: str) -> bool:
        """Delete data from Supabase table"""
        if not self.connected:
            return False

        try:
            result = self.client.table(collection).delete().eq('id', key).execute()
            logger.info(f"✅ Deleted record {key} from {collection}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete data from {collection}: {e}")
            return False

    def list_collections(self) -> List[str]:
        """List available Supabase tables"""
        # Note: Supabase doesn't provide a direct way to list tables via client
        # This would need to be configured manually or use REST API
        return ['signals', 'whale_rankings', 'strategy_metadata', 'user_subscriptions', 'api_keys']

# =============================================================================
# 🔥 FIREBASE IMPLEMENTATION
# =============================================================================

class FirebaseStorage(CloudStorageInterface):
    """Firebase cloud storage implementation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to Firebase"""
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            # Initialize Firebase app if not already initialized
            if not firebase_admin._apps:
                cred = credentials.Certificate({
                    "type": "service_account",
                    "project_id": self.config['project_id'],
                    "private_key": self.config['private_key'].replace('\\n', '\n'),
                    "client_email": self.config['client_email']
                })
                firebase_admin.initialize_app(cred)

            self.db = firestore.client()
            self.connected = True
            logger.info("✅ Connected to Firebase")
            return True
        except ImportError:
            logger.error("❌ Firebase library not installed. Install with: pip install firebase-admin")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to connect to Firebase: {e}")
            return False

    def store_data(self, collection: str, data: Union[Dict, List], key: Optional[str] = None) -> bool:
        """Store data in Firebase collection"""
        if not self.connected:
            return False

        try:
            if isinstance(data, list):
                # Bulk write
                batch = self.db.batch()
                for item in data:
                    doc_ref = self.db.collection(collection).document(key or str(time.time()))
                    batch.set(doc_ref, item)
                batch.commit()
            else:
                # Single document
                doc_ref = self.db.collection(collection).document(key or str(time.time()))
                doc_ref.set(data)

            logger.info(f"✅ Stored {len(data) if isinstance(data, list) else 1} documents in {collection}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to store data in {collection}: {e}")
            return False

    def retrieve_data(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve data from Firebase collection"""
        if not self.connected:
            return []

        try:
            collection_ref = self.db.collection(collection)

            if query:
                # Apply filters
                for key, value in query.items():
                    collection_ref = collection_ref.where(key, '==', value)

            if limit:
                collection_ref = collection_ref.limit(limit)

            docs = collection_ref.stream()
            data = [doc.to_dict() for doc in docs]
            logger.info(f"✅ Retrieved {len(data)} documents from {collection}")
            return data
        except Exception as e:
            logger.error(f"❌ Failed to retrieve data from {collection}: {e}")
            return []

    def update_data(self, collection: str, key: str, updates: Dict) -> bool:
        """Update data in Firebase collection"""
        if not self.connected:
            return False

        try:
            doc_ref = self.db.collection(collection).document(key)
            doc_ref.update(updates)
            logger.info(f"✅ Updated document {key} in {collection}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update data in {collection}: {e}")
            return False

    def delete_data(self, collection: str, key: str) -> bool:
        """Delete data from Firebase collection"""
        if not self.connected:
            return False

        try:
            doc_ref = self.db.collection(collection).document(key)
            doc_ref.delete()
            logger.info(f"✅ Deleted document {key} from {collection}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete data from {collection}: {e}")
            return False

    def list_collections(self) -> List[str]:
        """List available Firebase collections"""
        # Firebase doesn't provide a direct way to list collections via client
        return ['signals', 'whale_rankings', 'strategy_metadata', 'user_subscriptions', 'api_keys']

# =============================================================================
# 🍃 MONGODB ATLAS IMPLEMENTATION
# =============================================================================

class MongoDBStorage(CloudStorageInterface):
    """MongoDB Atlas cloud storage implementation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.db = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to MongoDB Atlas"""
        try:
            from pymongo import MongoClient
            self.client = MongoClient(self.config['connection_string'])
            self.db = self.client[self.config['database_name']]

            # Test connection
            self.client.admin.command('ping')
            self.connected = True
            logger.info("✅ Connected to MongoDB Atlas")
            return True
        except ImportError:
            logger.error("❌ PyMongo library not installed. Install with: pip install pymongo")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB Atlas: {e}")
            return False

    def store_data(self, collection: str, data: Union[Dict, List], key: Optional[str] = None) -> bool:
        """Store data in MongoDB collection"""
        if not self.connected:
            return False

        try:
            coll = self.db[collection]

            if isinstance(data, list):
                # Bulk insert
                result = coll.insert_many(data)
                inserted_count = len(result.inserted_ids)
            else:
                # Single insert
                if key:
                    data['_id'] = key
                result = coll.insert_one(data)
                inserted_count = 1

            logger.info(f"✅ Stored {inserted_count} documents in {collection}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to store data in {collection}: {e}")
            return False

    def retrieve_data(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve data from MongoDB collection"""
        if not self.connected:
            return []

        try:
            coll = self.db[collection]
            cursor = coll.find(query or {})

            if limit:
                cursor = cursor.limit(limit)

            data = list(cursor)
            # Convert ObjectId to string for JSON serialization
            for doc in data:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])

            logger.info(f"✅ Retrieved {len(data)} documents from {collection}")
            return data
        except Exception as e:
            logger.error(f"❌ Failed to retrieve data from {collection}: {e}")
            return []

    def update_data(self, collection: str, key: str, updates: Dict) -> bool:
        """Update data in MongoDB collection"""
        if not self.connected:
            return False

        try:
            coll = self.db[collection]
            from bson import ObjectId
            result = coll.update_one({'_id': ObjectId(key)}, {'$set': updates})
            logger.info(f"✅ Updated document {key} in {collection}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ Failed to update data in {collection}: {e}")
            return False

    def delete_data(self, collection: str, key: str) -> bool:
        """Delete data from MongoDB collection"""
        if not self.connected:
            return False

        try:
            coll = self.db[collection]
            from bson import ObjectId
            result = coll.delete_one({'_id': ObjectId(key)})
            logger.info(f"✅ Deleted document {key} from {collection}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"❌ Failed to delete data from {collection}: {e}")
            return False

    def list_collections(self) -> List[str]:
        """List available MongoDB collections"""
        if not self.connected:
            return []

        try:
            return self.db.list_collection_names()
        except Exception as e:
            logger.error(f"❌ Failed to list collections: {e}")
            return []

# =============================================================================
# ☁️ AWS S3 IMPLEMENTATION
# =============================================================================

class S3Storage(CloudStorageInterface):
    """AWS S3 cloud storage implementation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.s3_client = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to AWS S3"""
        try:
            import boto3
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.config['access_key_id'],
                aws_secret_access_key=self.config['secret_access_key'],
                region_name=self.config['region']
            )

            # Test connection
            self.s3_client.head_bucket(Bucket=self.config['bucket'])
            self.connected = True
            logger.info("✅ Connected to AWS S3")
            return True
        except ImportError:
            logger.error("❌ Boto3 library not installed. Install with: pip install boto3")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to connect to AWS S3: {e}")
            return False

    def store_data(self, collection: str, data: Union[Dict, List], key: Optional[str] = None) -> bool:
        """Store data as JSON file in S3 bucket"""
        if not self.connected:
            return False

        try:
            # Create S3 key (path)
            if key:
                s3_key = f"{collection}/{key}.json"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                s3_key = f"{collection}/{timestamp}.json"

            # Convert data to JSON
            if isinstance(data, list):
                json_data = json.dumps(data, default=str, indent=2)
            else:
                json_data = json.dumps(data, default=str, indent=2)

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.config['bucket'],
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )

            logger.info(f"✅ Stored data in S3: s3://{self.config['bucket']}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to store data in S3: {e}")
            return False

    def retrieve_data(self, collection: str, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve data from S3 bucket (limited functionality for query/filtering)"""
        if not self.connected:
            return []

        try:
            # List objects in collection prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.config['bucket'],
                Prefix=f"{collection}/"
            )

            data = []
            if 'Contents' in response:
                objects = response['Contents']
                if limit:
                    objects = objects[:limit]

                for obj in objects:
                    # Get object content
                    obj_response = self.s3_client.get_object(
                        Bucket=self.config['bucket'],
                        Key=obj['Key']
                    )

                    content = obj_response['Body'].read().decode('utf-8')
                    json_data = json.loads(content)

                    # Basic filtering if query provided
                    if query and isinstance(json_data, dict):
                        if all(json_data.get(k) == v for k, v in query.items()):
                            data.append(json_data)
                    else:
                        data.append(json_data)

            logger.info(f"✅ Retrieved {len(data)} objects from S3 {collection}")
            return data
        except Exception as e:
            logger.error(f"❌ Failed to retrieve data from S3: {e}")
            return []

    def update_data(self, collection: str, key: str, updates: Dict) -> bool:
        """Update data in S3 (retrieve, modify, re-upload)"""
        # S3 doesn't support direct updates, so we need to retrieve and re-upload
        try:
            # First retrieve existing data
            s3_key = f"{collection}/{key}.json"
            obj_response = self.s3_client.get_object(
                Bucket=self.config['bucket'],
                Key=s3_key
            )
            content = obj_response['Body'].read().decode('utf-8')
            existing_data = json.loads(content)

            # Apply updates
            existing_data.update(updates)

            # Re-upload
            json_data = json.dumps(existing_data, default=str, indent=2)
            self.s3_client.put_object(
                Bucket=self.config['bucket'],
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )

            logger.info(f"✅ Updated data in S3: s3://{self.config['bucket']}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update data in S3: {e}")
            return False

    def delete_data(self, collection: str, key: str) -> bool:
        """Delete data from S3 bucket"""
        if not self.connected:
            return False

        try:
            s3_key = f"{collection}/{key}.json"
            self.s3_client.delete_object(
                Bucket=self.config['bucket'],
                Key=s3_key
            )
            logger.info(f"✅ Deleted data from S3: s3://{self.config['bucket']}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete data from S3: {e}")
            return False

    def list_collections(self) -> List[str]:
        """List available S3 prefixes (collections)"""
        if not self.connected:
            return []

        try:
            # List top-level prefixes
            response = self.s3_client.list_objects_v2(
                Bucket=self.config['bucket'],
                Delimiter='/'
            )

            collections = []
            if 'CommonPrefixes' in response:
                collections = [prefix['Prefix'].rstrip('/') for prefix in response['CommonPrefixes']]

            return collections
        except Exception as e:
            logger.error(f"❌ Failed to list S3 collections: {e}")
            return []

# =============================================================================
# 🎯 CLOUD STORAGE MANAGER
# =============================================================================

class CloudStorageManager:
    """Unified cloud storage manager supporting multiple providers"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.storage_provider = None
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the appropriate storage provider"""
        provider_type = self.config.get('type', 'supabase')

        if provider_type == 'supabase':
            self.storage_provider = SupabaseStorage(self.config)
        elif provider_type == 'firebase':
            self.storage_provider = FirebaseStorage(self.config)
        elif provider_type == 'mongodb':
            self.storage_provider = MongoDBStorage(self.config)
        elif provider_type == 'aws_s3':
            self.storage_provider = S3Storage(self.config)
        else:
            raise ValueError(f"Unsupported storage provider: {provider_type}")

    def connect(self) -> bool:
        """Connect to cloud storage"""
        return self.storage_provider.connect()

    def store_trading_signals(self, signals: List[Dict]) -> bool:
        """Store trading signals data"""
        return self.storage_provider.store_data('signals', signals)

    def store_whale_rankings(self, rankings: List[Dict]) -> bool:
        """Store whale wallet rankings"""
        return self.storage_provider.store_data('whale_data', rankings)

    def store_strategy_metadata(self, metadata: List[Dict]) -> bool:
        """Store strategy performance metadata"""
        return self.storage_provider.store_data('strategy_metadata', metadata)

    def store_executed_trades(self, trades: List[Dict]) -> bool:
        """Store executed trades data"""
        return self.storage_provider.store_data('executed_trades', trades)

    def get_trading_signals(self, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve trading signals"""
        return self.storage_provider.retrieve_data('signals', query, limit)

    def get_whale_rankings(self, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve whale rankings"""
        return self.storage_provider.retrieve_data('whale_data', query, limit)

    def get_strategy_metadata(self, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve strategy metadata"""
        return self.storage_provider.retrieve_data('strategy_metadata', query, limit)

    def get_executed_trades(self, query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve executed trades"""
        return self.storage_provider.retrieve_data('executed_trades', query, limit)

    def update_data(self, collection: str, key: str, updates: Dict) -> bool:
        """Update data in specified collection"""
        return self.storage_provider.update_data(collection, key, updates)

    def delete_data(self, collection: str, key: str) -> bool:
        """Delete data from specified collection"""
        return self.storage_provider.delete_data(collection, key)

    def list_collections(self) -> List[str]:
        """List available collections"""
        return self.storage_provider.list_collections()

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on storage connection"""
        connected = self.storage_provider.connected if self.storage_provider else False
        collections = self.list_collections() if connected else []

        return {
            'provider': self.config.get('type', 'unknown'),
            'connected': connected,
            'collections': collections,
            'timestamp': datetime.now().isoformat()
        }

# =============================================================================
# 🏭 FACTORY FUNCTION
# =============================================================================

def get_cloud_storage_manager() -> CloudStorageManager:
    """
    Factory function to create cloud storage manager

    Returns:
        Configured CloudStorageManager instance
    """
    from .config import get_cloud_config
    config = get_cloud_config()
    return CloudStorageManager(config)

# =============================================================================
# 🧪 TEST FUNCTIONS
# =============================================================================

def test_cloud_storage():
    """Test cloud storage functionality"""
    try:
        manager = get_cloud_storage_manager()
        connected = manager.connect()

        if connected:
            print("✅ Cloud storage connection successful")

            # Test basic operations
            test_data = {
                'test_key': 'test_value',
                'timestamp': datetime.now().isoformat()
            }

            # Store test data
            success = manager.storage_provider.store_data('test_collection', test_data, 'test_key')
            if success:
                print("✅ Data storage successful")

                # Retrieve test data
                data = manager.storage_provider.retrieve_data('test_collection', {'test_key': 'test_value'})
                if data:
                    print("✅ Data retrieval successful")
                else:
                    print("❌ Data retrieval failed")

                # Clean up
                manager.storage_provider.delete_data('test_collection', 'test_key')
                print("✅ Test cleanup successful")
            else:
                print("❌ Data storage failed")
        else:
            print("❌ Cloud storage connection failed")

    except Exception as e:
        print(f"❌ Cloud storage test failed: {e}")

if __name__ == "__main__":
    test_cloud_storage()
